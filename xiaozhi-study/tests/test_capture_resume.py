"""Collector restart policy without USB access, subprocesses or runtime writes."""

from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, call, patch

from app.device import capture_control, device_registry


def usb_port(serial, port):
    return SimpleNamespace(serial_number=serial, device=port)


class ResumeRegisteredTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.registry = self.stack.enter_context(
            patch.object(capture_control, '_load', return_value={})
        )
        self.ports = self.stack.enter_context(
            patch.object(capture_control.usb_identity, 'camera_ports', return_value=[])
        )
        self.blocked = self.stack.enter_context(
            patch.object(device_registry, 'blocked', return_value=False)
        )
        self.start = self.stack.enter_context(
            patch.object(capture_control, 'set_running', return_value={'running': True})
        )

    def test_resumes_registered_physical_serial_on_same_or_changed_com_port(self):
        for current_port in ('COM9', 'COM12'):
            with self.subTest(current_port=current_port):
                self.start.reset_mock()
                self.registry.return_value = {
                    'KNOWN001': {'pid': 1234, 'port': 'COM9', 'device_id': 'registered-camera'}
                }
                self.ports.return_value = [usb_port('KNOWN001', current_port)]

                result = capture_control.resume_registered()

                self.start.assert_called_once_with(
                    True, port=current_port, device_id='registered-camera', restore=False
                )
                self.assertEqual(result, {
                    'collectors': [{
                        'device_id': 'registered-camera', 'port': current_port, 'running': True
                    }],
                    'errors': []
                })

    def test_explicitly_stopped_collectors_are_not_resumed(self):
        self.registry.return_value = {
            'KNOWN001': {'pid': None, 'port': 'COM9', 'device_id': 'stopped-camera'}
        }
        self.ports.return_value = [usb_port('KNOWN001', 'COM9')]

        self.assertEqual(capture_control.resume_registered(), {'collectors': [], 'errors': []})
        self.start.assert_not_called()

    def test_removed_devices_are_not_resumed_or_unblocked(self):
        self.registry.return_value = {
            'KNOWN001': {'pid': 1234, 'port': 'COM9', 'device_id': 'removed-camera'}
        }
        self.ports.return_value = [usb_port('KNOWN001', 'COM9')]
        self.blocked.return_value = True

        self.assertEqual(capture_control.resume_registered(), {'collectors': [], 'errors': []})
        self.start.assert_not_called()
        self.blocked.assert_called_once_with('removed-camera')

    def test_unplugged_device_is_not_replaced_by_a_different_usb_unit(self):
        self.registry.return_value = {
            'KNOWN001': {'pid': 1234, 'port': 'COM9', 'device_id': 'registered-camera'}
        }
        # Reusing the previous COM number is not proof of physical identity.
        self.ports.return_value = [usb_port('OTHER002', 'COM9')]

        self.assertEqual(capture_control.resume_registered(), {'collectors': [], 'errors': []})
        self.start.assert_not_called()

    def test_unknown_device_or_unregistered_usb_unit_needs_manual_connection(self):
        self.registry.return_value = {
            'KNOWN001': {'pid': 1234, 'port': 'COM9', 'device_id': None}
        }
        self.ports.return_value = [usb_port('KNOWN001', 'COM9'), usb_port('NEWUNIT2', 'COM12')]

        self.assertEqual(capture_control.resume_registered(), {'collectors': [], 'errors': []})
        self.start.assert_not_called()

    def test_one_collector_failure_does_not_prevent_other_collectors_resuming(self):
        self.registry.return_value = {
            'KNOWN001': {'pid': 1234, 'port': 'COM9', 'device_id': 'busy-camera'},
            'KNOWN002': {'pid': 5678, 'port': 'COM12', 'device_id': 'available-camera'}
        }
        self.ports.return_value = [usb_port('KNOWN001', 'COM9'), usb_port('KNOWN002', 'COM12')]
        self.start.side_effect = [RuntimeError('port busy'), {'running': True}]

        result = capture_control.resume_registered()

        self.assertEqual(self.start.call_args_list, [
            call(True, port='COM9', device_id='busy-camera', restore=False),
            call(True, port='COM12', device_id='available-camera', restore=False)
        ])
        self.assertEqual(result, {
            'collectors': [{'device_id': 'available-camera', 'port': 'COM12', 'running': True}],
            'errors': [{'device_id': 'busy-camera', 'error': 'port busy'}]
        })


class CollectorRestoreFlagTests(unittest.TestCase):
    def test_automatic_resume_does_not_pass_device_restoration_flag(self):
        for restore in (False, True):
            with self.subTest(restore=restore), ExitStack() as stack:
                stack.enter_context(patch.object(
                    capture_control, '_rows', return_value=([], [usb_port('KNOWN001', 'COM9')], {})
                ))
                stack.enter_context(patch.object(capture_control, 'RUNTIME_DIR', MagicMock()))
                save = stack.enter_context(patch.object(capture_control, '_save'))
                stack.enter_context(patch.object(capture_control, 'status', return_value={'running': True}))
                spawn = stack.enter_context(patch.object(
                    capture_control.subprocess, 'Popen', return_value=SimpleNamespace(pid=9999)
                ))

                self.assertEqual(capture_control.set_running(
                    True, port='COM9', device_id='registered-camera', restore=restore
                ), {'running': True})

                spawn.assert_called_once()
                args = spawn.call_args.args[0]
                self.assertEqual('--restore' in args, restore)
                self.assertEqual(args[args.index('--usb-serial') + 1], 'KNOWN001')
                self.assertEqual(args[args.index('--port') + 1], 'COM9')
                save.assert_called_once_with({
                    'KNOWN001': {'pid': 9999, 'port': 'COM9', 'device_id': 'registered-camera'}
                })


if __name__ == '__main__':
    unittest.main()
