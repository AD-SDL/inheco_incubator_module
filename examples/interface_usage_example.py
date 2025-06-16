"""
Example file to demonstrate usage of the tekmatic incubator interface through python

This example assumes two devices in one stack. Please edit to suit your needs.
"""

import time

# make sure you're running this example somewhere that allows importing this interface
import inheco_incubator_interface

print("Opening connection to the device stack over the COM port")
device_stack = inheco_incubator_interface.Interface(port="COM5")

# you can also specify dll path and Com port like this...
# device_stack = inheco_incubator_interface.Interface(port="COM5", dll_path=r"C:\\Program Files\\INHECO\\Incubator-Control\\ComLib.dll")

print("initilizing both devices")
device_stack.initialize_device(stack_floor=0)
device_stack.initialize_device(stack_floor=1)

print("Reporting any error flags")
print(f"Stack floor 0: {device_stack.report_error_flags(stack_floor=0)}")
print(f"Stack floor 1: {device_stack.report_error_flags(stack_floor=1)}")

print("Report actual temperature")
print(f"Stack floor 0: {device_stack.get_actual_temperature(stack_floor=0)}")
print(f"Stack floor 1: {device_stack.get_actual_temperature(stack_floor=1)}")

print("Report target temperature")
print(f"Stack floor 0: {device_stack.get_target_temperature(stack_floor=0)}")
print(f"Stack floor 1: {device_stack.get_target_temperature(stack_floor=1)}")

print("Set the target temperature to 30.0 deg C")
device_stack.set_target_temperature(stack_floor=0, temperature=30.0)
device_stack.set_target_temperature(stack_floor=1, temperature=30.0)

print("Turn the heater on then off - Stack floor 0")
device_stack.start_heater(stack_floor=0)
time.sleep(10)
device_stack.stop_heater(stack_floor=0)

print("Turn the heater on then off - Stack floor 1")
device_stack.start_heater(stack_floor=1)
time.sleep(10)
device_stack.stop_heater(stack_floor=1)

print("Is the heater active? (should be off)")
print(f"Stack floor 0: {device_stack.is_heater_active(stack_floor=0)}")
print(f"Stack floor 0: {device_stack.is_heater_active(stack_floor=0)}")

print("Open then close the door - Stack floor 0")
device_stack.open_door(stack_floor=0)
time.sleep(5)
device_stack.close_door(stack_floor=0)

print("Open then close the door - Stack floor 1")
device_stack.open_door(stack_floor=1)
time.sleep(5)
device_stack.close_door(stack_floor=1)

print("Is the door open? (should be closed)")
print(f"Stack floor 0: {device_stack.report_door_status(stack_floor=0)}")
print(f"Stack floor 1: {device_stack.report_door_status(stack_floor=1)}")

print("Is any labware present in the incubator?")
print(f"Stack floor 0: {device_stack.report_labware(stack_floor=0)}")
print(f"Stack floor 0: {device_stack.report_labware(stack_floor=1)}")

print("Set the shaker parameters - Stack floor 0")
device_stack.set_shaker_parameters(stack_floor=0, amplitude=2, frequency=14)

print("Set the shaker parameters - Stack floor 1")
device_stack.set_shaker_parameters(stack_floor=1, amplitude=2, frequency=14)

print("Start then stop the shaker - Stack floor 0")
device_stack.start_shaker(stack_floor=0)
time.sleep(10)  # shake for 10 seconds
device_stack.stop_shaker(stack_floor=0)

print("Start then stop the shaker - Stack floor 1")
device_stack.start_shaker(stack_floor=1)
time.sleep(10)  # shake for 10 seconds
device_stack.stop_shaker(stack_floor=1)

print("Is the shaker active? (should be inactive)")
print(f"Stack floor 0: {device_stack.is_shaker_active(stack_floor=0)}")
print(f"Stack floor 1: {device_stack.is_shaker_active(stack_floor=1)}")

print("Reset device settings - Stack floor 0")
device_stack.reset_device(stack_floor=0)

print("Reset device settings - Stack floor 1")
device_stack.reset_device(stack_floor=1)

print("Close the connection over the COM port")
device_stack.close_connection()
