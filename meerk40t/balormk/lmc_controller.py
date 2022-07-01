import threading
import time
from copy import copy

from meerk40t.balormk.mock_connection import MockConnection
from meerk40t.balormk.usb_connection import USBConnection
from meerk40t.device.basedevice import DRIVER_STATE_RAPID, DRIVER_STATE_PROGRAM
from meerk40t.fill.fills import Wobble
from meerk40t.kernel import (
    STATE_ACTIVE,
    STATE_BUSY,
    STATE_END,
    STATE_IDLE,
    STATE_INITIALIZE,
    STATE_PAUSE,
    STATE_SUSPEND,
    STATE_TERMINATE,
    STATE_UNKNOWN,
)


nop = [0x02, 0x80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
empty = bytearray(nop * 0x100)

listJumpTo = 0x8001
listEndOfList = 0x8002
listLaserOnPoint = 0x8003
listDelayTime = 0x8004
listMarkTo = 0x8005
listJumpSpeed = 0x8006
listLaserOnDelay = 0x8007
listLaserOffDelay = 0x8008
listMarkFreq = 0x800A
listMarkPowerRatio = 0x800B
listMarkSpeed = 0x800C
listJumpDelay = 0x800D
listPolygonDelay = 0x800F
listWritePort = 0x8011
listMarkCurrent = 0x8012
listMarkFreq2 = 0x8013
listFlyEnable = 0x801A
listQSwitchPeriod = 0x801B
listDirectLaserSwitch = 0x801C
listFlyDelay = 0x801D
listSetCo2FPK = 0x801E
listFlyWaitInput = 0x801F
listFiberOpenMO = 0x8021
listWaitForInput = 0x8022
listChangeMarkCount = 0x8023
listSetWeldPowerWave = 0x8024
listEnableWeldPowerWave = 0x8025
listFiberYLPMPulseWidth = 0x8026
listFlyEncoderCount = 0x8028
listSetDaZWord = 0x8029
listJptSetParam = 0x8050
listReadyMark = 0x8051

DisableLaser = 0x0002
EnableLaser = 0x0004
ExecuteList = 0x0005
SetPwmPulseWidth = 0x0006
GetVersion = 0x0007
GetSerialNo = 0x0009
GetListStatus = 0x000A
GetPositionXY = 0x000C
GotoXY = 0x000D
LaserSignalOff = 0x000E
LaserSignalOn = 0x000F
WriteCorLine = 0x0010
ResetList = 0x0012
RestartList = 0x0013
WriteCorTable = 0x0015
SetControlMode = 0x0016
SetDelayMode = 0x0017
SetMaxPolyDelay = 0x0018
SetEndOfList = 0x0019
SetFirstPulseKiller = 0x001A
SetLaserMode = 0x001B
SetTiming = 0x001C
SetStandby = 0x001D
SetPwmHalfPeriod = 0x001E
StopExecute = 0x001F
StopList = 0x0020
WritePort = 0x0021
WriteAnalogPort1 = 0x0022
WriteAnalogPort2 = 0x0023
WriteAnalogPortX = 0x0024
ReadPort = 0x0025
SetAxisMotionParam = 0x0026
SetAxisOriginParam = 0x0027
AxisGoOrigin = 0x0028
MoveAxisTo = 0x0029
GetAxisPos = 0x002A
GetFlyWaitCount = 0x002B
GetMarkCount = 0x002D
SetFpkParam2 = 0x002E
Fiber_SetMo = 0x0033  # open and close set by value
Fiber_GetStMO_AP = 0x0034
EnableZ = 0x003A
DisableZ = 0x0039
SetZData = 0x003B
SetSPISimmerCurrent = 0x003C
SetFpkParam = 0x0062
Reset = 0x0040
GetFlySpeed = 0x0038
FiberPulseWidth = 0x002F
FiberGetConfigExtend = 0x0030
InputPort = 0x0031  # ClearLockInputPort calls 0x04, then if EnableLockInputPort 0x02 else 0x01, GetLockInputPort
GetMarkTime = 0x0041
GetUserData = 0x0036
SetFlyRes = 0x0032

single_command_lookup = {
    0x0002: "DisableLaser",
    0x0004: "EnableLaser",
    0x0005: "ExecuteList",
    0x0006: "SetPwmPulseWidth",
    0x0007: "GetVersion",
    0x0009: "GetSerialNo",
    0x000A: "GetListStatus",
    0x000C: "GetPositionXY",
    0x000D: "GotoXY",
    0x000E: "LaserSignalOff",
    0x000F: "LaserSignalOn",
    0x0010: "WriteCorLine",
    0x0012: "ResetList",
    0x0013: "RestartList",
    0x0015: "WriteCorTable",
    0x0016: "SetControlMode",
    0x0017: "SetDelayMode",
    0x0018: "SetMaxPolyDelay",
    0x0019: "SetEndOfList",
    0x001A: "SetFirstPulseKiller",
    0x001B: "SetLaserMode",
    0x001C: "SetTiming",
    0x001D: "SetStandby",
    0x001E: "SetPwmHalfPeriod",
    0x001F: "StopExecute",
    0x0020: "StopList",
    0x0021: "WritePort",
    0x0022: "WriteAnalogPort1",
    0x0023: "WriteAnalogPort2",
    0x0024: "WriteAnalogPortX",
    0x0025: "ReadPort",
    0x0026: "SetAxisMotionParam",
    0x0027: "SetAxisOriginParam",
    0x0028: "AxisGoOrigin",
    0x0029: "MoveAxisTo",
    0x002A: "GetAxisPos",
    0x002B: "GetFlyWaitCount",
    0x002D: "GetMarkCount",
    0x002E: "SetFpkParam2",
    0x0033: "Fiber_SetMo",
    0x0034: "Fiber_GetStMO_AP",
    0x003A: "EnableZ",
    0x0039: "DisableZ",
    0x003B: "SetZData",
    0x003C: "SetSPISimmerCurrent",
    0x0062: "SetFpkParam",
    0x0040: "Reset",
    0x0038: "GetFlySpeed",
    0x002F: "FiberPulseWidth",
    0x0030: "FiberGetConfigExtend",
    0x0031: "InputPort",
    0x0041: "GetMarkTime",
    0x0036: "GetUserData",
    0x0032: "SetFlyRes",
}

BUSY = 0x04
READY = 0x20


class GalvoController:
    """
    Galvo controller is tasked with sending queued data to the controller board and ensuring that the connection to the
    controller board is established to perform these actions.

    This should serve as a next generation command sequencer written from scratch for galvo lasers. The goal is to
    provide all the given commands in a coherent queue structure which provides correct sequences between list and
    single commands.
    """

    def __init__(self, service, x=0x8000, y=0x8000, mark_speed=None, goto_speed=None, light_speed=None, dark_speed=None):
        self.service = service
        self.is_shutdown = False  # Shutdown finished.

        self.max_attempts = 5
        self.refused_count = 0
        self.count = 0

        name = self.service.label
        self.usb_log = service.channel(f"{name}/usb", buffer_size=500)
        self.usb_log.watch(lambda e: service.signal("pipe;usb_status", e))

        self.connection = None

        self._light_bit = service.setting(int, "light_pin", 8)
        self._foot_bit = service.setting(int, "footpedal_pin", 15)
        self._active_list = None
        self._active_index = 0
        self._last_x = x
        self._last_y = y
        self._mark_speed = mark_speed
        self._goto_speed = goto_speed
        self._light_speed = light_speed
        self._dark_speed = dark_speed

        self._ready = None
        self._speed = None
        self._travel_speed = None
        self._frequency = None
        self._power = None
        self._pulse_width = None

        self._delay_jump = None
        self._delay_on = None
        self._delay_off = None
        self._delay_poly = None
        self._delay_end = None

        self._wobble = None
        self._port_bits = 0
        self._machine_index = 0
        self.mode = DRIVER_STATE_RAPID

    def added(self):
        pass

    def service_detach(self):
        pass

    def shutdown(self, *args, **kwargs):
        self.is_shutdown = True

    def connect_if_needed(self):
        if self.connection is None:
            if self.service.setting(bool, "mock", False):
                self.connection = MockConnection(self.usb_log)
                name = self.service.label
                self.connection.send = self.service.channel(f"{name}/send")
                self.connection.recv = self.service.channel(f"{name}/recv")
            else:
                self.connection = USBConnection(self.usb_log)
        while not self.connection.is_open(self._machine_index):
            try:
                v = self.connection.open(self._machine_index)
                if v < 0:
                    self.count += 1
                    time.sleep(0.3)
                    continue
                self.init_laser()
            except (ConnectionError, ConnectionRefusedError):
                self.connection.close(self._machine_index)
                self.refused_count += 1
                time.sleep(0.5)
                continue

    def send(self, data):
        if self.is_shutdown:
            return
        self.connect_if_needed()
        self.connection.write(self._machine_index, data)

    def status(self):
        self.read_port()
        status = self.connection.read(self._machine_index)
        return status

    def _command_to_bytes(self, command, v1=0, v2=0, v3=0, v4=0, v5=0):
        return bytes(
            [
                command & 0xFF,
                command >> 8 & 0xFF,
                v1 & 0xFF,
                v1 >> 8 & 0xFF,
                v2 & 0xFF,
                v2 >> 8 & 0xFF,
                v3 & 0xFF,
                v3 >> 8 & 0xFF,
                v4 & 0xFF,
                v4 >> 8 & 0xFF,
                v5 & 0xFF,
                v5 >> 8 & 0xFF,
            ]
        )


    #######################
    # MODE SHIFTS
    #######################


    def rapid_mode(self):
        if self.mode != DRIVER_STATE_RAPID:
            self._list_end()
            self.mode = DRIVER_STATE_RAPID

    def program_mode(self):
        if self.mode != DRIVER_STATE_PROGRAM:
            self.mode = DRIVER_STATE_PROGRAM
            self.list_ready()
            # self.list_delay_time(0x0320)
            self.list_write_port()
            self.list_jump_speed(self.service.default_rapid_speed)

    def set_settings(self, settings):
        """
        Sets the primary settings. Rapid, frequency, speed, and timings.

        @param settings: The current settings dictionary
        @return:
        """
        if self.service.pulse_width_enabled:
            # Global Pulse Width is enabled.
            if str(settings.get("pulse_width_enabled", False)).lower() == "true":
                # Local Pulse Width value is enabled.
                # OpFiberYLPMPulseWidth

                self.list_fiber_ylpm_pulse_width(
                    int(settings.get("pulse_width", self.service.default_pulse_width))
                )
            else:
                # Only global is enabled, use global pulse width value.
                self.list_fiber_ylpm_pulse_width(self.service.default_pulse_width)

        if str(settings.get("rapid_enabled", False)).lower() == "true":
            self.list_jump_speed(
                float(settings.get("rapid_speed", self.service.default_rapid_speed))
            )
        else:
            self.list_jump_speed(self.service.default_rapid_speed)

        self.power(
            (float(settings.get("power", self.service.default_power)) / 10.0)
        )  # Convert power, out of 1000
        self.frequency(
            float(settings.get("frequency", self.service.default_frequency))
        )
        self.list_mark_speed(float(settings.get("speed", self.service.default_speed)))

        if str(settings.get("timing_enabled", False)).lower() == "true":
            self.list_laser_on_delay(
                settings.get("delay_laser_on", self.service.delay_laser_on)
            )
            self.list_laser_off_delay(
                settings.get("delay_laser_off", self.service.delay_laser_off)
            )
            self.list_polygon_delay(
                settings.get("delay_laser_polygon", self.service.delay_polygon)
            )
        else:
            # Use globals
            self.list_laser_on_delay(self.service.delay_laser_on)
            self.list_laser_off_delay(self.service.delay_laser_off)
            self.list_polygon_delay(self.service.delay_polygon)

    def set_wobble(self, settings):
        """
        Set the wobble parameters and mark modifications routines.

        @param settings: The dict setting to extract parameters from.
        @return:
        """
        if settings is None:
            self._wobble = None
            return
        wobble_enabled = str(settings.get("wobble_enabled", False)).lower() == "true"
        if not wobble_enabled:
            self._wobble = None
            return
        wobble_radius = settings.get("wobble_radius", "1.5mm")
        wobble_r = self.service.physical_to_device_length(wobble_radius, 0)[0]
        wobble_interval = settings.get("wobble_interval", "0.3mm")
        wobble_speed = settings.get("wobble_speed", 50.0)
        wobble_type = settings.get("wobble_type", "circle")
        wobble_interval = self.service.physical_to_device_length(wobble_interval, 0)[0]
        algorithm = self.service.lookup(f"wobble/{wobble_type}")
        if self._wobble is None:
            self._wobble = Wobble(
                algorithm=algorithm,
                radius=wobble_r,
                speed=wobble_speed,
                interval=wobble_interval,
            )
        else:
            # set our parameterizations
            self._wobble.algorithm = algorithm
            self._wobble.radius = wobble_r
            self._wobble.speed = wobble_speed

    #######################
    # PLOTLIKE SHORTCUTS
    #######################

    def mark(self, x, y):
        self.list_mark_speed(self._mark_speed)
        if self._wobble:
            for wx, wy in self._wobble(self._last_x, self._last_y, x, y):
                self.list_mark(wx, wy)
        else:
            self.list_mark(x, y)

    def goto(self, x, y, long=None, short=None, distance_limit=None):
        self.list_jump_speed(self._goto_speed)
        self.list_jump(x, y, long=long, short=short, distance_limit=distance_limit)

    def light(self, x, y, long=None, short=None, distance_limit=None):
        if self.light_on():
            self.list_write_port()
        self.list_jump_speed(self._light_speed)
        self.list_jump(x, y, long=long, short=short, distance_limit=distance_limit)

    def dark(self, x, y, long=None, short=None, distance_limit=None):
        if self.light_off():
            self.list_write_port()
        self.list_jump_speed(self._dark_speed)
        self.list_jump(x, y, long=long, short=short, distance_limit=distance_limit)

    def set_xy(self, x, y):
        self.goto_xy(x, y)

    def get_last_xy(self):
        return self._last_x, self._last_y

    #######################
    # Command Shortcuts
    #######################

    def is_busy(self):
        status = self.status()
        return bool(status & BUSY)

    def is_ready(self):
        status = self.status()
        return bool(status & READY)

    def is_ready_and_not_busy(self):
        status = self.status()
        return bool(status & READY) and not bool(status & BUSY)

    def wait_finished(self):
        while not self.is_ready_and_not_busy():
            time.sleep(0.01)

    def wait_ready(self):
        while not self.is_ready():
            time.sleep(0.01)

    def wait_idle(self):
        while self.is_busy():
            time.sleep(0.01)

    def abort(self):
        self.stop_execute()
        self.set_fiber_mo(0)
        self.reset_list()
        self.send(empty)
        self.set_end_of_list(1)
        self.execute_list()

    def pause(self):
        pass

    def resume(self):
        pass

    def init_laser(self):
        cor_file = self.service.corfile if self.service.corfile_enabled else None
        first_pulse_killer = self.service.first_pulse_killer
        pwm_pulse_width = self.service.pwm_pulse_width
        pwm_half_period = self.service.pwm_half_period
        standby_param_1 = self.service.standby_param_1
        standby_param_2 = self.service.standby_param_2
        timing_mode = self.service.timing_mode
        delay_mode = self.service.delay_mode
        laser_mode = self.service.laser_mode
        control_mode = self.service.control_mode
        fpk2_p1 = self.service.fpk2_p1
        fpk2_p2 = self.service.fpk2_p2
        fpk2_p3 = self.service.fpk2_p3
        fpk2_p4 = self.service.fpk2_p3
        fly_res_p1 = self.service.fly_res_p1
        fly_res_p2 = self.service.fly_res_p2
        fly_res_p3 = self.service.fly_res_p3
        fly_res_p4 = self.service.fly_res_p4
        self.reset()
        self.write_correction_file(cor_file)
        self.set_control_mode(control_mode)
        self.set_laser_mode(laser_mode)
        self.set_delay_mode(delay_mode)
        self.set_timing(timing_mode)
        self.set_standby(standby_param_1, standby_param_2)
        self.set_first_pulse_killer(first_pulse_killer)
        self.set_pwm_half_period(pwm_half_period)
        self.set_pwm_pulse_width(pwm_pulse_width)
        self.set_fiber_mo(0)  # Close
        self.set_pfk_param_2(fpk2_p1, fpk2_p2, fpk2_p3, fpk2_p4)
        self.set_fly_res(fly_res_p1, fly_res_p2, fly_res_p3, fly_res_p4)
        self.enable_z()
        self.write_analog_port_1(0x7FF)
        self.enable_z()

    def flush(self):
        self.wait_finished()
        self.reset_list()
        self.port_on(bit=0)
        self.set_fiber_mo(1)

        self.set_fiber_mo(0)

    def power(self, power):
        """
        Accepts power in percent, automatically converts to power_ratio

        @param power:
        @return:
        """
        if self._power == power:
            return
        self._power = power
        self.list_mark_power_ratio(self._convert_power(power))

    def frequency(self, frequency):
        if self._frequency == frequency:
            return
        self._frequency = frequency
        self.list_qswitch_period(self._convert_frequency(frequency))

    def light_on(self):
        if self.is_port(self._light_bit):
            self.port_on(self._light_bit)
            return True
        return False

    def light_off(self):
        if not self.is_port(self._light_bit):
            self.port_off(self._light_bit)
            return True
        return False

    def is_port(self, bit):
        return bool((1 << bit) & self._port_bits)

    def port_on(self, bit):
        self._port_bits = self._port_bits | (1 << bit)

    def port_off(self, bit):
        self._port_bits = ~((~self._port_bits) | (1 << bit))

    def port_set(self, mask, values):
        self._port_bits &= ~mask  # Unset mask.
        self._port_bits |= values & mask  # Set masked bits.

    #######################
    # LIST APPENDING OPERATIONS
    #######################

    def _list_end(self):
        if self._active_list:
            self.send(self._active_list)
            self._active_list = None
            self._active_index = 0

    def _list_new(self):
        self._active_list = copy(empty)
        self._active_index = 0

    def _list_write(self, command, v1=0, v2=0, v3=0, v4=0, v5=0):
        if self._active_index >= 0xC00:
            self._list_end()
        if self._active_list is None:
            self._list_new()
        self._active_list[
            self._active_index : self._active_list + 12
        ] = self._command_to_bytes(command, v1, v2, v3, v4, v5)
        self._active_index += 12

    def _command(self, command, v1=0, v2=0, v3=0, v4=0, v5=0):
        self._list_end()
        cmd = self._command_to_bytes(command, v1, v2, v3, v4, v5)
        self.send(cmd)

    #######################
    # UNIT CONVERSIONS
    #######################

    def _convert_speed(self, speed):
        """
        mm/s speed implies a distance but the galvo head doesn't move mm and doesn't know what lens you are currently
        using which changes the definition of what a mm is, this calculation is likely naive for a particular lens size
        and needs to be scaled according the other relevant factors.

        @param speed:
        @return:
        """
        return int(speed / 2.0)

    def _convert_frequency(self, frequency_khz):
        """
        Converts frequency to period.

        20000000.0 / frequency in hz

        @param frequency_khz: Frequency to convert
        @return:
        """
        return int(round(20000.0 / frequency_khz))

    def _convert_power(self, power):
        """
        Converts power percent to int value
        @return:
        """
        return int(round(power * 0xFFF / 100.0))

    #######################
    # HIGH LEVEL OPERATIONS
    #######################

    def write_correction_file(self, filename):
        if filename is None:
            self.write_blank_correct_file()
            return
        try:
            table = self._read_correction_file(filename)
            self._write_correction_table(table)
        except IOError:
            self.write_blank_correct_file()
            return

    def write_blank_correct_file(self):
        self.write_cor_table(False)
        # for i in range(65 * 65):
        #     self.write_cor_line(0, 0, 0 if i == 0 else 1)

    def _read_correction_file(self, filename):
        """
        Reads a standard .cor file and builds a table from that.

        @param filename:
        @return:
        """
        table = []
        with open(filename, "rb") as f:
            f.seek(0x24)
            for j in range(65):
                for k in range(65):
                    dx = int.from_bytes(f.read(4), "little", signed=True)
                    dx = dx if dx >= 0 else -dx + 0x8000
                    dy = int.from_bytes(f.read(4), "little", signed=True)
                    dy = dy if dy >= 0 else -dy + 0x8000
                    table.append([dx & 0xFFFF, dy & 0xFFFF])
        return table

    def _write_correction_table(self, table):
        assert len(table) == 65 * 65
        self.write_cor_table(True)
        first = True
        for dx, dy in table:
            self.write_cor_line(dx, dy, 0 if first else 1)
            first = False

    #######################
    # COMMAND LIST COMMAND
    #######################

    def list_jump(self, x, y, short=None, long=None, distance_limit=None):
        distance = int(abs(complex(x, y) - complex(self._last_x, self._last_y)))
        if distance_limit and distance > distance_limit:
            time = long
        else:
            time = short
        if distance > 0xFFFF:
            distance = 0xFFFF
        angle = 0
        if time:
            self.list_jump_delay(time)
        self._list_write(listJumpTo, int(x), int(y), angle, distance)

    def list_end_of_list(self):
        self._list_write(listEndOfList)

    def list_laser_on_point(self, dwell_time):
        self._list_write(listLaserOnPoint, dwell_time)

    def list_delay_time(self, time):
        """
        Delay time in microseconds units

        @param time:
        @return:
        """
        self._list_write(listDelayTime, time)

    def list_mark(self, x, y, angle=0):
        distance = int(abs(complex(x, y) - complex(self._last_x, self._last_y)))
        if distance > 0xFFFF:
            distance = 0xFFFF
        self._list_write(listMarkTo, x, y, angle, distance)

    def list_jump_speed(self, speed):
        if self._travel_speed == speed:
            return
        self._travel_speed = speed
        self._list_write(listJumpSpeed, self._convert_speed(speed))

    def list_laser_on_delay(self, delay):
        """
        Set laser on delay in microseconds
        @param delay:
        @return:
        """
        if self._delay_on == delay:
            return
        self._delay_on = delay
        sign = 0
        if delay < 0:
            sign = 0x8000
        self._list_write(listLaserOnDelay, delay, sign)

    def list_laser_off_delay(self, delay):
        """
        Set laser off delay in microseconds
        @param delay:
        @return:
        """
        if self._delay_off == delay:
            return
        self._delay_off = delay
        sign = 0
        if delay < 0:
            sign = 0x8000
        self._list_write(listLaserOffDelay, delay, sign)

    def list_mark_frequency(self, frequency):
        """
        This command is used in some machines but it's not clear given the amount of reverse engineering how those
        values are set. This is done for laser_type = 4.

        @param frequency:
        @return:
        """
        # listMarkFreq
        raise NotImplementedError

    def list_mark_power_ratio(self, power_ratio):
        """
        This command is used in some machines. Laser_type=4 and laser_type=0 (CO2), if 0x800A returned 0.

        @param power_ratio:
        @return:
        """
        # listMarkPowerRatio
        self._list_write(listMarkPowerRatio, power_ratio)

    def list_mark_speed(self, speed):
        """
        Sets the marking speed for the laser.

        @param speed:
        @return:
        """
        if self._speed == speed:
            return
        self._speed = speed
        self._list_write(self._convert_speed(speed))

    def list_jump_delay(self, delay):
        """
        Set laser jump delay in microseconds
        @param delay:
        @return:
        """
        if self._delay_jump == delay:
            return
        self._delay_jump = delay
        sign = 0
        if delay < 0:
            sign = 0x8000
        self._list_write(listJumpDelay, delay, sign)

    def list_polygon_delay(self, delay):
        """
        Set polygon delay in microseconds
        @param delay:
        @return:
        """
        if self._delay_poly == delay:
            return
        self._delay_poly = delay
        sign = 0
        if delay < 0:
            sign = 0x8000
        self._list_write(listPolygonDelay, delay, sign)

    def list_write_port(self):
        """
        Writes the set port values to the list.

        @return:
        """
        self._list_write(listWritePort, self._port_bits)

    def list_mark_current(self, current):
        """
        Also called as part of setting the power ratio. This is not correctly understood.
        @param current:
        @return:
        """
        # listMarkCurrent
        raise NotImplementedError

    def list_mark_frequency_2(self, frequency):
        """
        Also called as part of setting frequency and is not correctly understood.

        @param frequency:
        @return:
        """
        # listMarkFreq2
        raise NotImplementedError

    def list_fly_enable(self, enabled=1):
        """
        On-The-Fly control enable/disable within list.

        @param enabled:
        @return:
        """
        self._list_write(listFlyEnable, enabled)

    def list_qswitch_period(self, qswitch):
        """
        Sets the qswitch period, which in is the inversely related to frequency.

        @param qswitch:
        @return:
        """
        self._list_write(listQSwitchPeriod, qswitch)

    def list_direct_laser_switch(self):
        """
        This is not understood.
        @return:
        """
        # ListDirectLaserSwitch
        raise NotImplementedError

    def list_fly_delay(self, delay):
        """
        On-the-fly control.

        @param delay:
        @return:
        """
        self._list_write(listFlyDelay, delay)

    def list_set_co2_fpk(self):
        """
        Set the CO2 Laser, First Pulse Killer.

        @return:
        """
        self._list_write(listSetCo2FPK)

    def list_fly_wait_input(self):
        """
        Sets the On-the-fly to wait for input.
        @return:
        """
        self._list_write(listFlyWaitInput)

    def list_fiber_open_mo(self, open_mo):
        """
        Sets motion operations, without MO set the laser does not automatically fire while moving.

        @param open_mo:
        @return:
        """
        self._list_write(listFiberOpenMO, open_mo)

    def list_wait_for_input(self, wait_state):
        """
        Unknown.

        @return:
        """
        self._list_write(listWaitForInput, wait_state)

    def list_change_mark_count(self, count):
        """
        Unknown.

        @param count:
        @return:
        """
        self._list_write(listChangeMarkCount, count)

    def list_set_weld_power_wave(self, weld_power_wave):
        """
        Unknown.

        @param weld_power_wave:
        @return:
        """
        self._list_write(listSetWeldPowerWave, weld_power_wave)

    def list_enable_weld_power_wave(self, enabled):
        """
        Unknown.

        @param enabled:
        @return:
        """
        self._list_write(listEnableWeldPowerWave, enabled)

    def list_fiber_ylpm_pulse_width(self, pulse_width):
        """
        Unknown.

        @param pulse_width:
        @return:
        """
        if self._pulse_width == pulse_width:
            return
        self._pulse_width = pulse_width
        self._list_write(listFiberYLPMPulseWidth, pulse_width)

    def list_fly_encoder_count(self, count):
        """
        Unknown.

        @param count:
        @return:
        """
        self._list_write(listFlyEncoderCount, count)

    def list_set_da_z_word(self, word):
        """
        Unknown.

        @param word:
        @return:
        """
        self._list_write(listSetDaZWord, word)

    def list_jpt_set_param(self, param):
        """
        Unknown.

        @param param:
        @return:
        """
        self._list_write(listJptSetParam, param)

    def list_ready(self):
        """
        Seen at the start of any new command list.

        @return:
        """
        self._list_write(listReadyMark)

    #######################
    # COMMAND LIST SHORTCUTS
    #######################

    def disable_laser(self):
        self._command(DisableLaser)

    def enable_laser(self):
        self._command(EnableLaser)

    def execute_list(self):
        self._command(ExecuteList)

    def set_pwm_pulse_width(self, pulse_width):
        self._command(SetPwmPulseWidth, pulse_width)

    def get_state(self):
        self._command(GetVersion)

    def get_serial_number(self):
        self._command(GetSerialNo)

    def get_list_status(self):
        self._command(GetListStatus)

    def get_position_xy(self):
        self._command(GetPositionXY)

    def goto_xy(self, x, y):
        self._command(GotoXY, int(x), int(y))

    def laser_signal_off(self):
        self._command(LaserSignalOff)

    def laser_signal_on(self):
        self._command(LaserSignalOn)

    def write_cor_line(self, dx, dy, non_first):
        self._command(WriteCorLine, dx, dy, non_first)

    def reset_list(self):
        self._command(ResetList)

    def restart_list(self):
        self._command(RestartList)

    def write_cor_table(self, table: bool = True):
        self._command(WriteCorTable, int(table))

    def set_control_mode(self, mode):
        self._command(SetControlMode, mode)

    def set_delay_mode(self, mode):
        self._command(SetDelayMode, mode)

    def set_max_poly_delay(self, delay):
        self._command(SetMaxPolyDelay, delay)

    def set_end_of_list(self, end):
        self._command(SetEndOfList, end)

    def set_first_pulse_killer(self, fpk):
        self._command(SetFirstPulseKiller, fpk)

    def set_laser_mode(self, mode):
        self._command(SetLaserMode, mode)

    def set_timing(self, timing):
        self._command(SetTiming, timing)

    def set_standby(self, standby1, standby2):
        self._command(SetStandby, standby1, standby2)

    def set_pwm_half_period(self, pwm_half_period):
        self._command(SetPwmPulseWidth, pwm_half_period)

    def stop_execute(self):
        self._command(StopExecute)

    def stop_list(self):
        self._command(StopList)

    def write_port(self):
        self._command(WritePort, self._port_bits)

    def write_analog_port_1(self, port):
        self._command(WriteAnalogPort1, port)

    def write_analog_port_2(self, port):
        self._command(WriteAnalogPort2, port)

    def write_analog_port_x(self, port):
        self._command(WriteAnalogPortX, port)

    def read_port(self):
        self._command(ReadPort)

    def set_axis_motion_param(self, param):
        self._command(SetAxisMotionParam, param)

    def set_axis_origin_param(self, param):
        self._command(SetAxisOriginParam, param)

    def axis_go_origin(self):
        self._command(AxisGoOrigin)

    def move_axis_to(self, a):
        self._command(MoveAxisTo)

    def get_axis_pos(self):
        self._command(GetAxisPos)

    def get_fly_wait_count(self):
        self._command(GetFlyWaitCount)

    def get_mark_count(self):
        self._command(GetMarkCount)

    def set_pfk_param_2(self, param1, param2, param3, param4):
        self._command(SetFpkParam2, param1, param2, param3, param4)

    def set_fiber_mo(self, mo):
        """
        mo == 0 close
        mo == 1 open

        @param mo:
        @return:
        """
        self._command(Fiber_SetMo, mo)

    def get_fiber_st_mo_ap(self):
        self._command(Fiber_GetStMO_AP)

    def enable_z(self):
        self._command(EnableZ)

    def disable_z(self):
        self._command(DisableZ)

    def set_z_data(self, zdata):
        self._command(SetZData, zdata)

    def set_spi_simmer_current(self, current):
        self._command(SetSPISimmerCurrent, current)

    def set_fpk_param(self, param):
        self._command(SetFpkParam, param)

    def reset(self):
        self._command(Reset)

    def get_fly_speed(self):
        self._command(GetFlySpeed)

    def fiber_pulse_width(self):
        self._command(FiberPulseWidth)

    def get_fiber_config_extend(self):
        self._command(FiberGetConfigExtend)

    def input_port(self, port):
        self._command(InputPort, port)

    def clear_lock_input_port(self):
        self._command(InputPort, 0x04)

    def enable_lock_input_port(self):
        self._command(InputPort, 0x02)

    def disable_lock_input_port(self):
        self._command(InputPort, 0x01)

    def get_input_port(self):
        self._command(InputPort)

    def get_mark_time(self):
        self._command(GetMarkTime)

    def get_user_data(self):
        self._command(GetUserData)

    def set_fly_res(self, fly_res1, fly_res2, fly_res3, fly_res4):
        self._command(SetFlyRes, fly_res1, fly_res2, fly_res3, fly_res4)
