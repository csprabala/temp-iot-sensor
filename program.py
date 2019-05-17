import random
import time
import sys
import math

import yaml

import iothub_client
# pylint: disable=E0611
from iothub_client import IoTHubClient, IoTHubClientError, IoTHubTransportProvider, IoTHubClientResult
from iothub_client import IoTHubMessage, IoTHubMessageDispositionResult, IoTHubError, DeviceMethodReturnValue

import serial
from serial.tools import list_ports

CONFIG = {}
with open('settings.yaml', 'r') as stream:
    CONFIG = yaml.load(stream)

# Using the MQTT protocol.
PROTOCOL = IoTHubTransportProvider.MQTT
MESSAGE_TIMEOUT = 10000

# Define the JSON message to send to IoT Hub.
TEMPERATURE = 65.0
HUMIDITY = 45
MSG_TXT = "{\"temperature\": %.2f,\"humidity\": %.2f,\"heatindex\": %.2f,\"dewpoint\": %.2f}}"

INTERVAL = 5

def send_confirmation_callback(message, result, user_context):
    print ( "IoT Hub responded to message with status: %s" % (result) )

def iothub_client_init(kind):
    # Create an IoT Hub client
    if(kind == "simulator"):
        client = IoTHubClient(CONFIG['simulator_connection_string'], PROTOCOL)
    else:
        client = IoTHubClient(CONFIG['sensor_connection_string'], PROTOCOL)
    # Set up the callback method for direct method calls from the hub.
    client.set_device_method_callback(
        device_method_callback, None)
            
    return client

# Handle direct method calls from IoT Hub
def device_method_callback(method_name, payload, user_context):
    global INTERVAL
    print ( "\nMethod callback called with:\nmethodName = %s\npayload = %s" % (method_name, payload) )
    device_method_return_value = DeviceMethodReturnValue()
    if method_name == "SetTelemetryInterval":
        try:
            INTERVAL = int(payload)
            # Build and send the acknowledgment.
            device_method_return_value.response = "{ \"Response\": \"Executed direct method %s\" }" % method_name
            device_method_return_value.status = 200
        except ValueError:
            # Build and send an error response.
            device_method_return_value.response = "{ \"Response\": \"Invalid parameter\" }"
            device_method_return_value.status = 400
    else:
        # Build and send an error response.
        device_method_return_value.response = "{ \"Response\": \"Direct method not defined: %s\" }" % method_name
        device_method_return_value.status = 404
    return device_method_return_value

def run():
    try:
        args = sys.argv
        if len(args) != 2:
            print("Usage: prorgam.py --simulate or program.py --sensor")
        else:
            args = args[1]
            if (args == "--simulate"):
                client = iothub_client_init("simulate")
                while True:
                    # Build the message with simulated telemetry values.
                    temperature = TEMPERATURE + (random.random() * 15)
                    humidity = HUMIDITY + (random.random() * 20)
                    heat_index = compute_heat_index(temperature, humidity)
                    dew_point = compute_dew_point(temperature, humidity)
                    msg_txt_formatted = MSG_TXT % (temperature, humidity, heat_index, dew_point)
                    message = IoTHubMessage(msg_txt_formatted)

                    # Add a custom application property to the message.
                    # An IoT hub can filter on these properties without access to the message body.
                    prop_map = message.properties()
                    prop_map.add("kind", "simulator")
                    # Send the message.
                    print( "Sending message: %s" % message.get_string() )
                    client.send_event_async(message, send_confirmation_callback, None)
                    time.sleep(INTERVAL)
            elif (args == "--sensor"):
                client = iothub_client_init("sensor")
                serial_port = get_serial_port()
                if serial_port is None:
                    print("Serial port unavailable to read data")
                    return
                print('Available serial port: '+serial_port)
                input = serial.Serial(serial_port, CONFIG['baud_rate'])
                # skip header
                input.readline()
                while True:
                    line = input.readline()
                    print(line)
                    sensor_data = line.split(b',')
                    msg_txt_formatted = MSG_TXT % (float(sensor_data[0]), float(sensor_data[1]), 
                        float(sensor_data[2]), float(sensor_data[3]))
                    message = IoTHubMessage(msg_txt_formatted)
                    prop_map = message.properties()
                    prop_map.add("kind", "sensor")
                    print( "Sending message: %s" % message.get_string() )
                    client.send_event_async(message, send_confirmation_callback, None)
            else:
                print("Choose from --simulate or --sensor")
                return   
    except IoTHubError as iothub_error:
        print ( "Unexpected error %s from IoTHub" % iothub_error )
        return
    except KeyboardInterrupt:
        print ( "IoTHubClient sample stopped" )


def get_serial_port():
    ports = list(serial.tools.list_ports.comports())  
    # return the port if 'USB' is in the description 
    for port_no, description, address in ports:
        if 'usb' in port_no:
            return port_no
        

def compute_dew_point(farenheit, humidity):
    a = 17.271
    b = 237.7
    celcius = (farenheit - 32) / 1.8;
    temp = (a * celcius) / (b + celcius) + math.log(humidity*0.01)
    td = (b * temp) / (a - temp);
    return td * 1.8 + 32

def compute_heat_index(farenheit, humidity):
    # Creating multiples of 'fahrenheit' & 'hum' values for the coefficients
    T2 = math.pow(farenheit, 2)
    H2 = math.pow(humidity, 2)

    # Coefficients for the calculations
    C1 = [ -42.379, 2.04901523, 10.14333127, -0.22475541, -6.83783e-03, -5.481717e-02, 1.22874e-03, 8.5282e-04, -1.99e-06]

    # Calculating heat-indexes with 3 different formula
    return C1[0] + (C1[1] * farenheit) + (C1[2] * humidity) + (C1[3] * farenheit * humidity) + (C1[4] * T2) + (C1[5] * H2) + (C1[6] * T2 * humidity) + (C1[7] * farenheit * H2) + (C1[8] * T2 * H2)
   
if __name__ == '__main__':
    print ( "Climate Sensor IoT Sample. ")
    print ( "Press Ctrl-C to exit" )
    run()