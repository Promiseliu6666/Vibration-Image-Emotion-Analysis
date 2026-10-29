"""SenseCAP Watcher USB camera bridge; keeps the existing ESP32 firmware."""
import argparse
import base64
import json
import logging
import time
import os
from concurrent.futures import ThreadPoolExecutor
from app.device import usb_identity
from pathlib import Path
import httpx
import serial
from serial.tools import list_ports

LOG = logging.getLogger('watcher-usb')

def find_camera_port():
    ports = usb_identity.camera_ports()
    if len(ports) != 1:
        raise RuntimeError('Connect one Watcher USB data cable; expected one CH342 SERIAL-A camera port')
    return ports[0].device

def messages(connection, command, timeout):
    connection.reset_input_buffer()
    connection.write(command.encode('ascii') + b'\r\n')
    connection.flush()
    pending = bytearray()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pending.extend(connection.read(min(65536, max(1, connection.in_waiting))))
        if len(pending) > 4 * 1024 * 1024:
            raise RuntimeError('Camera response exceeded 4 MB')
        while b'\n' in pending:
            newline = pending.find(b'\n')
            line = bytes(pending[:newline])
            del pending[:newline + 1]
            try:
                value = json.loads(line.strip())
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(value, dict):
                yield value

def connect(port, expected_serial=None):
    before = usb_identity.port_info(port)
    if expected_serial and usb_identity.normalize(before.serial_number)!=expected_serial:raise RuntimeError("USB identity changed; refusing a different physical camera")
    connection = serial.Serial(port=None, baudrate=921600, timeout=.02, write_timeout=2)
    connection.dtr = False
    connection.rts = False
    connection.port = port
    connection.open()
    try:
        for message in messages(connection, 'AT+ID?', 3):
            if message.get('name') == 'ID?' and message.get('code') == 0:
                after = usb_identity.port_info(port)
                if before.serial_number != after.serial_number:
                    raise RuntimeError('USB device changed during identification')
                identity = usb_identity.identify(after.serial_number, message.get('data'))
                LOG.info('Camera identified on %s: %s', port, identity['device_id'])
                return connection, identity
        raise RuntimeError('No SSCMA camera identification response')
    except Exception:
        connection.close()
        raise

def capture(connection):
    for message in messages(connection, 'AT+SAMPLE=1', 10):
        if message.get('name') != 'SAMPLE':
            continue
        if message.get('code') != 0:
            raise RuntimeError('Camera sample failed: ' + str(message.get('code')))
        data = message.get('data')
        if isinstance(data, dict) and data.get('image'):
            jpeg = base64.b64decode(data['image'], validate=True)
            if not jpeg.startswith(b'\xff\xd8'):
                raise RuntimeError('Camera did not return a JPEG')
            return jpeg
    raise RuntimeError('Camera sample timed out')

def capture_batch(connection, count=16):
    delivered = 0
    for message in messages(connection, f'AT+SAMPLE={count}', max(15, count)):
        if message.get('name') != 'SAMPLE':
            continue
        if message.get('code') != 0:
            raise RuntimeError('Camera batch sample failed')
        data = message.get('data')
        if isinstance(data, dict) and data.get('image'):
            jpeg = base64.b64decode(data['image'], validate=True)
            if not jpeg.startswith(b'\xff\xd8'):
                raise RuntimeError('Camera did not return a JPEG')
            yield jpeg
            delivered += 1
            if delivered >= count:
                return
    raise RuntimeError('Camera batch sample timed out')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', help='Optional SERIAL-A port; auto-detected by default')
    parser.add_argument('--usb-serial', help='Pin this collector to one physical USB serial')
    parser.add_argument('--server', default='http://127.0.0.1:8000')
    parser.add_argument('--restore', action='store_true', help='Explicitly allow re-adding the identified physical unit')
    parser.add_argument('--interval', type=float, default=.06)
    parser.add_argument('--frames', type=int, default=0, help='0 keeps capturing until stopped')
    args = parser.parse_args()
    if args.interval < .04 or args.frames < 0:
        parser.error('interval must be >= 0.04 and frames >= 0')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    connection = None
    identity = None
    restore = args.restore
    sent = 0
    last_state_write = 0
    capture_times = []
    def state(error=None):
        usb_identity.write_state(dict(usb_serial=args.usb_serial,pid=os.getpid(),port=connection.port if connection else None,
                                      connected=connection is not None,identity=identity if connection else None,
                                      error=error,updated_at=time.time(),capture_fps=round((len(capture_times)-1)/(capture_times[-1]-capture_times[0]),2) if len(capture_times)>1 and capture_times[-1]>capture_times[0] else None))
    state()
    def upload(client, jpeg, device_id):
        response = client.post('/upload/frame', params={'device_id':device_id}, content=jpeg, headers={'Content-Type':'image/jpeg'})
        response.raise_for_status()
        if response.json().get('status') != 'ok':
            raise RuntimeError('Backend rejected frame')
    pending_upload = None
    samples = None
    try:
        with httpx.Client(base_url=args.server, timeout=httpx.Timeout(15, connect=2, write=5, pool=5), trust_env=False) as client, ThreadPoolExecutor(max_workers=1, thread_name_prefix='camera-upload') as uploader:
            while args.frames == 0 or sent < args.frames:
                started = time.monotonic()
                try:
                    if connection is None:
                        connection, identity = connect(args.port or find_camera_port(),args.usb_serial)
                        from app.device import device_registry
                        if restore:
                            device_registry.set_blocked(identity['device_id'], False)
                            restore = False
                        if device_registry.blocked(identity['device_id']):
                            raise RuntimeError('This physical device was removed; use the connect wizard to restore it')
                        state()
                        # Restore clear sensor output; use batch sampling to reduce command overhead.
                        for reply in messages(connection, 'AT+SENSOR=1,1,3', 3):
                            if reply.get('name') == 'SENSOR':
                                if reply.get('code') != 0:
                                    LOG.warning('Smooth camera profile unavailable; retaining device default')
                                break
                    if args.frames:
                        jpeg = capture(connection)
                    else:
                        if samples is None:
                            samples = capture_batch(connection)
                        try:
                            jpeg = next(samples)
                        except StopIteration:
                            samples = capture_batch(connection)
                            jpeg = next(samples)
                    capture_times.append(time.monotonic())
                    capture_times[:] = capture_times[-40:]
                    # One upload in flight, no queued old frames. Sampling never waits for HTTP.
                    if args.frames:
                        upload(client, jpeg, identity['device_id'])
                        sent += 1
                    else:
                        if pending_upload is not None and pending_upload.done():
                            pending_upload.result()
                            pending_upload = None
                            sent += 1
                        if pending_upload is None:
                            pending_upload = uploader.submit(upload, client, jpeg, identity['device_id'])
                    if sent and sent % 100 == 0:
                        LOG.debug('Delivered %d frames, device=%s', sent, identity['device_id'])
                    if time.monotonic() - last_state_write >= 1:
                        state()
                        last_state_write = time.monotonic()
                except (serial.SerialException, OSError, RuntimeError, ValueError, httpx.HTTPError) as error:
                    if pending_upload is not None:
                        try: pending_upload.result(timeout=6)
                        except Exception: pass
                        pending_upload = None
                    samples = None
                    network_error = isinstance(error, httpx.HTTPError)
                    if connection is not None and not network_error:
                        connection.close()
                        connection = None
                    state(('项目连接暂未就绪：' if network_error else '设备读取未完成，请检查 USB 或重新检测：')+str(error))
                    if args.frames:
                        raise
                    LOG.warning('%s; retrying in 3 seconds', error)
                    time.sleep(3)
                time.sleep(max(0, args.interval - (time.monotonic() - started)))
    except KeyboardInterrupt:
        LOG.info('Capture stopped')
    finally:
        if connection is not None:
            connection.close()
        connection = None
        state()

if __name__ == '__main__':
    main()
