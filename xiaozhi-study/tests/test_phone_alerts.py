import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from app.analysis.phone_alerts import PhoneAlerts

PHONE = {'person_present': True, 'learning_state': 'distracted_phone'}
READING = {'person_present': True, 'learning_state': 'engaged_reading'}


class PhoneAlertTests(IsolatedAsyncioTestCase):
    async def test_persistence_cooldown_and_physical_device_isolation(self):
        alerts = PhoneAlerts()
        with patch('app.analysis.phone_alerts.play_usb', return_value=('played', None)) as speaker:
            alerts.observe('device-a', PHONE, 100)
            alerts.observe('device-a', PHONE, 102)
            self.assertEqual(speaker.call_count, 0)
            alerts.observe('device-a', PHONE, 104)
            await asyncio.gather(*alerts.tasks)
            self.assertEqual(speaker.call_count, 1)
            last = alerts.devices['device-a']['last_reminded']
            for timestamp in [last + 1, last + 3, last + 5]:
                alerts.observe('device-a', PHONE, timestamp)
            self.assertEqual(speaker.call_count, 1)
            for timestamp in [last + 1, last + 3, last + 5]:
                alerts.observe('device-b', PHONE, timestamp)
            await asyncio.gather(*alerts.tasks)
            self.assertEqual(speaker.call_count, 2)
            self.assertEqual(speaker.call_args.args, ('device-b',))
            alerts.observe('device-a', READING, last + 10)
            self.assertFalse(alerts.snapshot('device-a')['active'])
            for timestamp in [last + 70, last + 72, last + 74]:
                alerts.observe('device-a', PHONE, timestamp)
            await asyncio.gather(*alerts.tasks)
            self.assertEqual(speaker.call_count, 3)

    async def test_frame_gap_and_absence_do_not_confirm_phone_use(self):
        alerts = PhoneAlerts()
        with patch('app.analysis.phone_alerts.play_usb') as speaker:
            for timestamp in [100, 102, 120]:
                alerts.observe('device-a', PHONE, timestamp)
            alerts.observe('device-b', {**PHONE, 'person_present': False}, 100)
            alerts.observe('device-c', PHONE, 100)
            alerts.observe('device-c', PHONE, 102)
            alerts.observe('device-c', PHONE, 104, fresh=False)
            self.assertTrue(alerts.snapshot('device-c')['stale'])
            self.assertFalse(alerts.snapshot('device-c')['active'])
            self.assertFalse(alerts.tasks)
            self.assertFalse(alerts.snapshot('device-b')['active'])
            speaker.assert_not_called()

    async def test_busy_or_unavailable_is_not_reported_as_played(self):
        for state in ['busy', 'unavailable', 'failed', 'muted']:
            alerts = PhoneAlerts()
            with patch('app.analysis.phone_alerts.play_usb', return_value=(state, 'not played')):
                for timestamp in [100, 102, 104]:
                    alerts.observe('device-a', PHONE, timestamp)
                await asyncio.gather(*alerts.tasks)
                self.assertEqual(alerts.snapshot('device-a')['voice_status'], state)
                self.assertIsNone(alerts.snapshot('device-a')['last_reminded'])

    async def test_disabled_phone_reminder_never_starts_playback(self):
        alerts = PhoneAlerts()
        with patch('app.analysis.phone_alerts.play_usb') as speaker:
            for timestamp in [100, 102, 104]:
                alerts.observe('device-a', PHONE, timestamp, enabled=False)
            self.assertEqual(alerts.snapshot('device-a')['voice_status'], 'disabled')
            self.assertFalse(alerts.snapshot('device-a')['active'])
            self.assertFalse(alerts.tasks)
            speaker.assert_not_called()

    async def test_custom_phone_interval_controls_repeat(self):
        alerts = PhoneAlerts()
        with patch('app.analysis.phone_alerts.play_usb', return_value=('played', None)) as speaker:
            for timestamp in [100, 102, 104]:
                alerts.observe('device-a', PHONE, timestamp, cooldown_seconds=300)
            await asyncio.gather(*alerts.tasks)
            self.assertEqual(speaker.call_count, 1)
            last = alerts.devices['device-a']['last_reminded']
            for timestamp in [last + 60, last + 62, last + 64]:
                alerts.observe('device-a', PHONE, timestamp, cooldown_seconds=300)
            self.assertEqual(speaker.call_count, 1)
            for timestamp in [last + 301, last + 303, last + 305]:
                alerts.observe('device-a', PHONE, timestamp, cooldown_seconds=300)
            await asyncio.gather(*alerts.tasks)
            self.assertEqual(speaker.call_count, 2)

    async def test_server_scheduler_owns_phone_playback(self):
        alerts = PhoneAlerts()
        with patch('app.analysis.phone_alerts.play_usb') as speaker:
            for timestamp in [100, 102, 104]:
                alerts.observe('device-a', PHONE, timestamp, managed_elsewhere=True)
            self.assertEqual(alerts.snapshot('device-a')['voice_status'], 'scheduler')
            self.assertFalse(alerts.tasks)
            speaker.assert_not_called()

    async def test_only_one_inflight_playback_per_device(self):
        alerts = PhoneAlerts()
        with patch('app.analysis.phone_alerts.play_usb', return_value=('played', None)) as speaker:
            self.assertTrue(alerts.start('device-a'))
            self.assertFalse(alerts.start('device-a'))
            await asyncio.gather(*alerts.tasks)
            speaker.assert_called_once()


class UsbSpeakerTests(IsolatedAsyncioTestCase):
    def test_scheduled_voice_uses_production_command(self):
        from app.analysis import phone_alerts
        calls=[]
        with patch.object(phone_alerts,'_console',side_effect=lambda *args,**kwargs:(calls.append(args),('played',None))[1]):
            status,error=phone_alerts.play_local_voice('device-a','posture')
        self.assertEqual((status,error),('played',None))
        self.assertEqual(calls[0][1],'study_voice_play posture')
        self.assertEqual(calls[0][2],'study_voice_ack')

    def test_physical_device_mismatch_never_opens_port(self):
        from app.analysis.phone_alerts import play_usb
        with patch('app.device.capture_control.status', return_value={'running': True, 'device_id': 'a'}), patch('serial.Serial') as port:
            status, _ = play_usb('b')
            self.assertEqual(status, 'unavailable')
            port.assert_not_called()

    def test_acknowledged_speaker_and_unsupported_firmware(self):
        from types import SimpleNamespace
        from app.analysis.phone_alerts import play_usb
        device = {'running': True, 'device_id': 'a', 'identity': {'usb_serial': 'physical-a'}}
        control = SimpleNamespace(device='COM6', serial_number='physical-a', description='USB SERIAL-B')
        for response, expected in [(b'{"type":"study_alert_ack","status":"played"}\n', 'played'),
                                   (b'{"type":"study_alert_ack","status":"busy"}\n', 'busy'),
                                   (b'{"type":"study_alert_ack","status":"muted"}\n', 'muted'),
                                   (b'Unrecognized command\n', 'unavailable')]:
            with patch('app.device.capture_control.status', return_value=device), patch('serial.tools.list_ports.comports', return_value=[control]), patch('serial.Serial') as serial_port:
                connection = serial_port.return_value
                connection.read.return_value = response
                connection.is_open = True
                status, _ = play_usb('a')
                self.assertEqual(status, expected)
                connection.write.assert_called_once_with(b'study_phone_alert\r\n')
                connection.close.assert_called_once()

    def test_device_replaced_before_command_is_blocked(self):
        from types import SimpleNamespace
        from app.analysis.phone_alerts import play_usb
        original = SimpleNamespace(device='COM6', serial_number='physical-a', description='USB SERIAL-B')
        replacement = SimpleNamespace(device='COM6', serial_number='physical-b', description='USB SERIAL-B')
        with patch('app.device.capture_control.status', return_value={'running': True, 'device_id': 'a', 'identity': {'usb_serial': 'physical-a'}}), patch('serial.tools.list_ports.comports', side_effect=[[original], [replacement]]), patch('serial.Serial') as serial_port:
            status, _ = play_usb('a')
            self.assertEqual(status, 'failed')
            serial_port.return_value.write.assert_not_called()

    def test_screen_state_command_is_utf8_and_acknowledged(self):
        from types import SimpleNamespace
        from app.analysis.phone_alerts import send_console
        device = {'running': True, 'device_id': 'a', 'identity': {'usb_serial': 'physical-a'}}
        control = SimpleNamespace(device='COM6', serial_number='physical-a', description='USB SERIAL-B')
        line = '投入阅读 · 连续用眼 8 分'
        with patch('app.device.capture_control.status', return_value=device), patch('serial.tools.list_ports.comports', return_value=[control]), patch('serial.Serial') as serial_port:
            connection = serial_port.return_value
            connection.read.return_value = b'{"type":"study_state_ack","status":"shown"}\n'
            connection.is_open = True
            status, error = send_console('a', 'study_state ' + line, 'study_state_ack')
            self.assertEqual((status, error), ('ok', None))
            connection.write.assert_called_once_with(('study_state ' + line + '\r\n').encode('utf-8'))

    def test_screen_state_never_interleaves_with_voice_playback(self):
        from app.analysis import phone_alerts
        self.assertTrue(phone_alerts._voice_lock.acquire(blocking=False))
        try:
            status, error = phone_alerts.send_console('a', 'study_state 投入阅读')
            self.assertEqual(status, 'busy')
            self.assertIn('串口', error)
        finally:
            phone_alerts._voice_lock.release()

    def test_missing_firmware_command_is_reported_as_unavailable(self):
        from types import SimpleNamespace
        from app.analysis.phone_alerts import send_console
        device = {'running': True, 'device_id': 'a', 'identity': {'usb_serial': 'physical-a'}}
        control = SimpleNamespace(device='COM6', serial_number='physical-a', description='USB SERIAL-B')
        with patch('app.device.capture_control.status', return_value=device), patch('serial.tools.list_ports.comports', return_value=[control]), patch('serial.Serial') as serial_port:
            connection = serial_port.return_value
            connection.read.return_value = b'Unrecognized command\n'
            connection.is_open = True
            status, error = send_console('a', 'study_state 投入阅读', 'study_state_ack')
            self.assertEqual(status, 'unavailable')
            self.assertIn('固件', error)
