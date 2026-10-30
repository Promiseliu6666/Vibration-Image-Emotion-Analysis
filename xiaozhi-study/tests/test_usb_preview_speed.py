import base64
import json
import watcher_usb

class CameraSerial:
    def __init__(self,chunks):self.chunks=list(chunks);self.requests=[];self.commands=[]
    @property
    def in_waiting(self):return len(self.chunks[0]) if self.chunks else 0
    def reset_input_buffer(self):pass
    def write(self,data):self.commands.append(data)
    def flush(self):pass
    def read(self,size):
        self.requests.append(size)
        if not self.chunks:return b''
        head=self.chunks[0];result=head[:size];self.chunks[0]=head[size:]
        if not self.chunks[0]:self.chunks.pop(0)
        return result

def test_camera_reads_available_bytes_and_handles_fragmented_lines():
    jpeg=b'\xff\xd8example\xff\xd9'
    payload=(json.dumps({'name':'SAMPLE','code':0,'data':{'image':base64.b64encode(jpeg).decode()}})+'\n').encode()
    camera=CameraSerial([b'{',payload[1:24],payload[24:]])
    assert watcher_usb.capture(camera)==jpeg
    assert camera.commands==[b'AT+SAMPLE=1\r\n']
    assert max(camera.requests)<65536

def test_acknowledgement_and_image_in_same_read_do_not_drop_image():
    jpeg=b'\xff\xd8valid\xff\xd9'
    camera=CameraSerial([b'{"name":"ACK","code":0}\n'+(json.dumps({'name':'SAMPLE','code':0,'data':{'image':base64.b64encode(jpeg).decode()}})+'\n').encode()])
    assert watcher_usb.capture(camera)==jpeg


def test_batch_uses_one_command_and_keeps_all_images():
    jpeg=b'\xff\xd8batch\xff\xd9'
    line=(json.dumps({'name':'SAMPLE','code':0,'data':{'image':base64.b64encode(jpeg).decode()}})+'\n').encode()
    camera=CameraSerial([line+line+line])
    assert list(watcher_usb.capture_batch(camera,3))==[jpeg]*3
    assert camera.commands==[b'AT+SAMPLE=3\r\n']
