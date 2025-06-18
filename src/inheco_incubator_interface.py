"""
Interface for controlling the Inheco Single Plate Incubator Shaker device.
"""

import argparse
import logging
import threading
import time
import traceback

import clr


class Interface:
    """
    Basic interface for Inheco Single Plate Incubator Shakers
    """

    def __init__(
        self,
        port,
        dll_path=r"C:\\Program Files\\INHECO\\Incubator-Control\\ComLib.dll",
    ):
        """Opens the connection to the incubator.

        Note: No need to initialize here. Initialization completed
        on startup of each module
        """
        # set up logger
        self.port = port  # COM port of the device(s)
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            filename="inheco_interface.log",
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )

        self.lock = threading.Lock()
        clr.AddReference(dll_path)
        from IncubatorCom import Com

        self.incubator_com = Com()
        self.open_connection()

    # DEVICE CONTROL
    def open_connection(self):
        """Opens the connection to the incubator over the specified COM port"""
        with self.lock:
            response = self.incubator_com.openCom(self.port)
            if response == 77:
                self.logger.info("Com connection opened successfully")
                print("Com connection opened successfully")  # helpful terminal message
            else:
                # response 170 means failed
                self.logger.error("Failed to open the Inheco incubator Com connection")
                raise Exception("Failed to open Inheco incubator Com connection")
            return response

    def close_connection(self):
        """Closes any existing open connection, no response expected on success or fail"""
        with self.lock:
            self.incubator_com.closeCom()
            self.logger.info("Com connection closed")
            print("Com connection closed")

    def initialize_device(self, stack_floor: int):
        """Initializes the Inheco Single Plate Incubator Shaker Device through the open connection."""
        self.send_message("AID", stack_floor=stack_floor, read_delay=3)
        self.logger.info(f"Inheco incubator initialized at stack floor {stack_floor}")
        print(f"Inheco incubator initialized at stack floor {stack_floor}")

    def reset_device(self, stack_floor: int) -> str:
        """Resets the Inheco Single Plate Incubator Device
        Note: seems to respond 88 regardless of success or failure
        """
        response = self.send_message(
            "SRS", stack_floor=stack_floor, read_delay=5
        )  # wait 5 seconds before reading response
        self.logger.info("device reset")
        return response

    def report_error_flags(self, stack_floor: int) -> str:
        """Reports any error flags present on device
        Responses:
            0 = no errors
        """
        response = self.send_message("REF", stack_floor=stack_floor)
        self.logger.debug(f"error flags response: {response}")
        return response

    # TEMPERATURE CONTROL
    def get_actual_temperature(self, stack_floor: int) -> float:
        """Returns the actual temperature as measured by main sensor on incubator (sensor 1).
        Note: There are two other sensors that we don't report. Get their values with "RAT2" and "RAT3" """
        response = self.send_message("RAT", stack_floor=stack_floor)
        temperature = float(response) / 10
        self.logger.info(f"get actual temperature: {temperature}")
        return temperature

    def get_target_temperature(self, stack_floor: int) -> float:
        """Returns the set target temperature of the incubator"""
        response = self.send_message("RTT", stack_floor=stack_floor)
        temperature = float(response) / 10
        self.logger.info(f"get target temperature: {temperature}")
        return temperature

    def set_target_temperature(
        self,
        stack_floor: int,
        temperature: float = 22.0,
    ):
        """Sets the target temperature, if no temperature specified, defaults to 22 deg C"""
        if 0 <= (int(temperature * 10)) <= 800:
            self.logger.info("setting target temperature")
            message = "STT" + str(int(temperature * 10))
            response = self.send_message(message, stack_floor=stack_floor)
            self.logger.debug(f"set target temperature com response: {response}")
            return response
        else:
            print("Error: temperature input invalid in set_target_temperature method")
            self.logger.error(
                "Error: temperature input invalid in set_target_temperature method"
            )

    def start_heater(self, stack_floor: int):
        """Enables the device heating element.
        Note: can read the set value with self.send_message("RHE"). 0 = off, 1 = on.
        """
        self.send_message("SHE1", stack_floor=stack_floor)
        self.logger.info("started heater")

    def stop_heater(self, stack_floor: int):
        """Disable the device heating element.
        Note: can read the set value with self.send_message("RHE"). 0 = off, 1 = on.
        """
        self.send_message("SHE", stack_floor=stack_floor)
        self.logger.info("stopped heater")

    def is_heater_active(self, stack_floor: int) -> bool:
        """Returns True if heater/cooler is activated, otherwise False"""
        response = self.send_message("RHE", stack_floor=stack_floor)

        try:
            response = int(response)
            if response == 0:  # 0 = off
                return False
            elif response in [1, 2]:  # 1 = on, 2 = on with booster
                return True
            else:
                raise Exception(
                    "Unexpected integer response from is_heater_active query"
                )
        except Exception as e:
            print(f"Unable to parse is_heater_active response: {response}")
            self.logger.error(
                f"Unable to parse is_heater_active response: {response}. {traceback.format_exc()}"
            )
            raise (e)

    # DOOR ACTIONS
    def open_door(self, stack_floor: int):
        """Opens the door"""
        self.send_message(
            "AOD",
            stack_floor=stack_floor,
            read_delay=6,
        )  # wait 6 seconds before reading com response
        self.logger.info("opened door")

    def close_door(self, stack_floor: int):
        """Closes the door"""
        self.send_message(
            "ACD",
            stack_floor=stack_floor,
            read_delay=7,
        )  # wait 7 seconds before reading com response
        self.logger.info("closed door")

    def report_door_status(self, stack_floor: int):
        """Determines if front incubator door is open.

        TODO: return true/false?

        Responses:
            0 = door closed
            1 = door open
        """
        response = self.send_message("RDS", stack_floor=stack_floor)
        self.logger.debug(f"door status (0 closed, 1 open): {response}")
        return response

    def report_labware(self, stack_floor: int):
        """Determines if labware is present in incubator

        TODO: return int?

        Responses:
            0 = no labware present
            1 = labware detected,
            8 = error, door open
            7 = error, reset and door closed
        """
        response = self.send_message("RLW", stack_floor=stack_floor)
        self.logger.debug(f"report labware response: {response}")

        return response

    # SHAKER COMMANDS
    def start_shaker(self, stack_floor: int, status="ND"):
        """Enables the device shaking element

        Arguments:
            status: (int or str) 1 = on, (str) "ND" = on without labware detection

        Returns:
            None
        """
        if status in [1, "1", "ND"]:
            self.send_message(
                "ASE" + str(status), stack_floor=stack_floor, read_delay=3
            )
            self.logger.info("started shaker")
        else:
            self.logger.error("Value Error: invalid status in start_shaker method")
            raise ValueError("Error: invalid status in start_shaker method")

    def stop_shaker(self, stack_floor: int):
        """Disables the device shaking element"""
        self.send_message("ASE0", stack_floor=stack_floor, read_delay=5)
        self.logger.info("stopped shaker")

    def is_shaker_active(self, stack_floor: int) -> bool:
        """Determines if incubator shaker is active.

        # TODO: should we be raising exceptions here?

        Returns:
            True = shaker is active
            False = shaker not active
        """
        response = self.send_message("RSE", stack_floor=stack_floor)
        try:
            response = int(response)
            if response in [0, 2]:
                self.logger.info("shaker is inactive")
                return False
            elif response == 1:
                self.logger.info("shaker is active")
                return True
            else:
                self.logger.error(f"unable to read shaker state: response = {response}")
                raise Exception("Unable to read shaker state")
        except Exception as e:
            self.logger.error(f"Unable to parse is_shaker_active response: {response}")
            print("Unable to parse is_shaker_active response")
            raise (e)

    def set_shaker_parameters(
        self, stack_floor: int, amplitude: float = 2.0, frequency: float = 14.2
    ):
        """Sets the shaking parameters

        Arguments:
            amplitude: (float) shaking distance in mm, 0.0-3.0 mm valid, 2.0 mm default
            frequency: (float) speed of shaking revolutions in Hz (1Hz = 60 rpm), 6.6-30.0 Hz valid, 14.2 default Hz

        Notes:
        - Through the dll there is support for controlling amplitude and frequency on x and y axes.
            That level of control is not supported here as it was deemed not necessary

        - Phase shift is also controllable through dll, we will keep it at 0 deg.

        - Read set values with: "RFX" (frequency x), "RFY" (frequency y), "RAX" (amplitude x), "RAY" (amplitude y), and "RPS" (phase shift)
        - Read actual values with: "RFX1", "RFY1", "RAX(1(actual) or 2(static measure))", "RAY(1(actual) or 2(static measure))", and "RPS1"
        """
        phase_shift = "000"

        # format inputs
        try:
            amplitude = int(amplitude * 10)
            frequency = int(frequency * 10)

            if 0 <= amplitude <= 30 and 66 <= frequency <= 300:
                # Message formatting = SSP + str(amplitude_x) + srt(amplitude_y) + str(frequency_x) + str(frequency_y) + str(phase_shift)
                self.send_message(
                    "SSP"
                    + str(amplitude)
                    + ","
                    + str(amplitude)
                    + ","
                    + str(frequency)
                    + ","
                    + str(frequency)
                    + ","
                    + str(phase_shift),
                    stack_floor=stack_floor,
                )
                self.logger.info("shaker parameters set")
            else:
                self.logger.error(
                    "Error: invalid amplitude or frequency input values in set_shaker_parameters method"
                )
                print(
                    "Error: invalid amplitude or frequency input values in set_shaker_parameters method"
                )

        except Exception as e:
            self.logger.error(f"Error: unable to set shaker parameters. {e}")
            self.logger.error(traceback.format_exc())
            print(f"Error: unable to set shaker parameters. {e}")
            raise e

    # HELPER COMMANDS
    def send_message(
        self, message_string, device_id=2, stack_floor=0, read_delay=0.5
    ) -> str:
        """Formats and sends message to Inheco Device, then collects device response

        Arguments:
            message_string: (str) message string to send to inheco device
            device_id: (int) ID of the inheco device that will receive the message, default 2
            stack_floor: (int) level of the inheco device. Need to specify in case several devices are stacked, default 0
            read_delay: (float) seconds to wait before reading com response, default .5 seconds

        Returns:
            formatted_response: response from the Com port without extra characters
        """

        with self.lock:
            # convert message length, device ID, and stack floor to bytes
            bytes_message_length = len(message_string) & 0xFF
            bytes_device_ID = device_id & 0xFF
            bytes_stack_floor = stack_floor & 0xFF

            # convert them message to byte array
            bytes_message = bytes([ord(c) for c in message_string])

            # format the message, send over com port and collect response
            self.incubator_com.sendMsg(
                bytes_message, bytes_message_length, bytes_device_ID, bytes_stack_floor
            )
            self.logger.debug(
                f"sent message: bytes_message={bytes_message}, bytes_message_length={bytes_message_length}, bytes_device_ID={bytes_device_ID}, bytes_stack_floor={bytes_stack_floor}"
            )

            time.sleep(read_delay)

            # Read COM port response
            response = self.incubator_com.readCom()
            self.logger.debug(f"sent message response: {response}")
            formatted_response = self.format_response(response, device_id=device_id)
            self.logger.debug(f"sent message formatted response: {formatted_response}")

            return formatted_response

    def format_response(self, response: str, device_id: int) -> str:
        """Extracts important message details from longer com response message

        Arguments:
            response: raw response from the Com port after a message is sent

        Returns:
            formatted_response: response from the Com port without extra characters

        Note: the extra characters relate to device id. They are not needed.
        """
        try:
            # remove extra characters
            formatted_response = response[1:]  # remove extra beginning characters
            formatted_response = formatted_response[:-4]

        except Exception as e:
            self.logger.debug(
                f"Device response ({response} could not be formatted. {e}"
            )

        # check for '#' response meaning invalid command was sent
        if formatted_response == "#":
            self.logger.debug("Error: invalid command sent, '#' response received")
            raise Exception("Error: invalid command sent, '#' response received")

        return formatted_response

    @property
    def is_busy(self) -> bool:
        """Returns True if incubator busy, False otherwise"""
        if self.lock.locked():
            return True
        else:
            return False


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "--device",
        type=str,
        help="Serial port for communicating with the device",
        default="COM5",
    )
    argparser.add_argument(
        "--dll_path",
        type=str,
        help="Path to inheco device dll",
        default="C:\\Program Files\\INHECO\\Incubator-Control\\ComLib.dll",
    )
    args = argparser.parse_args()
    device = args.device
    dll_path = args.dll_path

    com = Interface(port=device, dll_path=dll_path)
    print(f"Inheco incubator device connected, {device}")
