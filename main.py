# Cat tracker python script

import argparse
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import sys
import threading
import time
from datetime import datetime
from uuid import uuid4
import json
import serial
from csv import DictWriter
import numpy as np

class DetectCat:

    def __init__(self):

        self.a_trigger_time = 0.0
        self.a_timer_running = False
        self.a_trigger_timeout = 10.0
        self.a_triggered = False

        self.b_trigger_time = 0.0
        self.b_timer_running = False
        self.b_trigger_timeout = 15.0
        self.b_triggered = False

        self.going_out = False
        self.going_in = False
        self.cat_inside = True

        self.trigger_time = [0.0, 0.0]
        self.timer_running = [0, 0]

        self.trigger_timeout = [10.0, 15.0]
        self.triggered = [False, False]

        # publishing
        self.publish_times = [00, 15, 30, 45]
        self.publish_timer_timeout = 80.0
        self.publish_timer_running = False
        self.publish_timer_secs = 0.0
        self.publish_current_time_sec = 0.0

    def detectTriggered(self, motions, dt):

        for idx, motion in enumerate(motions):

            # turn off timer after 10s
            if self.trigger_time[idx] > self.trigger_timeout[idx]:
                self.timer_running[idx] = False
                self.trigger_time[idx] = 0.0

            # if timer not already running
            if not self.timer_running[idx]:

                # if theres motion
                if motion:
                    self.triggered[idx] = True
                    self.timer_running[idx] = True

            # print("timer running: " + str(self.timer_running))
            if self.timer_running[idx]:
                self.trigger_time[idx] += dt

            # keep true until time window expires
            if self.triggered[idx] and not self.timer_running[idx]:
                self.triggered[idx] = False

        return self.triggered

    def detectInOut(self, a_trig, b_trig):

        if a_trig and not b_trig:
            self.going_out = True

        if b_trig and not a_trig:
            self.going_in = True

        if self.going_out and b_trig:
            self.cat_inside = False

        if self.going_in and a_trig:
            self.cat_inside = True

        # reset
        if not a_trig and not b_trig:
            self.going_in = False
            self.going_out = False

        return self.cat_inside

    def publish(self, message, message_dict, topic, connection, dt):

        time_now = datetime.now()
        current_time_min = int(time_now.strftime("%M"))

        for _time in self.publish_times:

            if _time == current_time_min:

                if not self.publish_timer_running:
                    # publish to DynamoDB
                    connection.publish(
                        topic=topic,
                        payload=message,
                        qos=mqtt.QoS.AT_LEAST_ONCE)

                    # save to CSV backup
                    field_names = ['Date', 'A_triggered', 'B_triggered', 'cat_inside']
                    with open('data.csv', 'a') as f_object:
                        dictwriter_object = DictWriter(f_object, fieldnames=field_names)
                        dictwriter_object.writerow(message_dict)
                        f_object.close()

                    print("--- Publishing ---")
                    self.publish_timer_running = True


        if self.publish_timer_running:
            self.publish_timer_secs += dt

        # turn off timer after 80s, reset timer
        if self.publish_timer_secs > self.publish_timer_timeout:
            self.publish_timer_running = False
            self.publish_timer_secs = 0.0

def parseArgs():
    parser = argparse.ArgumentParser(description="Send and receive messages through and MQTT connection.")
    parser.add_argument('--endpoint', default="*********")
    parser.add_argument('--port', type=int, help="Specify port. AWS IoT supports 443 and 8883.")
    parser.add_argument('--cert', default="*********")
    parser.add_argument('--key', default="*********")
    parser.add_argument('--root-ca', default="*********")
    parser.add_argument('--client-id', default="test-" + str(uuid4()))

    # Using globals to simplify sample code
    args = parser.parse_args()
    return args

# Callback when connection is accidentally lost.
def on_connection_interrupted(connection, error, **kwargs):
    print("Connection interrupted. error: {}".format(error))

# Callback when an interrupted connection is re-established.
def on_connection_resumed(connection, return_code, session_present, **kwargs):
    print("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        print("Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
        # evaluate result with a callback instead.
        resubscribe_future.add_done_callback(on_resubscribe_complete)

def on_resubscribe_complete(resubscribe_future):
    resubscribe_results = resubscribe_future.result()
    print("Resubscribe results: {}".format(resubscribe_results))

    for topic, qos in resubscribe_results['topics']:
        if qos is None:
            sys.exit("Server rejected resubscribe to topic: {}".format(topic))


# Callback when the subscribed topic receives a message
def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    print("Received message from topic '{}': {}".format(topic, payload))
    global received_count
    received_count += 1
    if received_count == args.count:
        received_all_event.set()


args = parseArgs()

topic = "sensor_data"

use_websocket = False
proxy_host = False
disconnect = False

io.init_logging(getattr(io.LogLevel, io.LogLevel.NoLogs.name), 'stderr')

received_count = 0
received_all_event = threading.Event()


if __name__ == '__main__':
    # Spin up resources
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)
    proxy_options = None

    if (proxy_host):
        proxy_options = http.HttpProxyOptions(host_name=args.proxy_host, port=8080)

    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=args.endpoint,
        port=args.port,
        cert_filepath=args.cert,
        pri_key_filepath=args.key,
        client_bootstrap=client_bootstrap,
        ca_filepath=args.root_ca,
        on_connection_interrupted=on_connection_interrupted,
        on_connection_resumed=on_connection_resumed,
        client_id=args.client_id,
        clean_session=False,
        keep_alive_secs=6,
        http_proxy_options=proxy_options)

    print("Connecting to {} with client ID '{}'...".format(
        args.endpoint, args.client_id))

    connect_future = mqtt_connection.connect()

    # Future.result() waits until a result is available
    connect_future.result()
    print("Connected!")

    detectCat = DetectCat()

    # Arduino port connection
    port = serial.Serial("/dev/ttyACM0", baudrate=115200)

    current_time_sec = 0.0

    while True:

        try:
            motions = port.readline()
            motions = motions.decode('latin-1')
            motions = motions.split()
        except:
            print("Could not connect...")

        if (len(motions) == 2):

            # timing
            prev_current_time_sec = current_time_sec
            current_time_sec = time.time()
            dt = current_time_sec - prev_current_time_sec

            triggered = detectCat.detectTriggered([int(motions[0]), int(motions[1])], dt)
            cat_inside = detectCat.detectInOut(a_trig=triggered[0], b_trig=triggered[1])

            if cat_inside:
                cat = "inside"
            else:
                cat = "outside"

            print(str(motions) + "\t" "A: " + str(triggered[0]) + "\t" + "B: " + str(triggered[1]) + "\t" + "Cat: " + cat)

            msg = json.dumps({'a_triggered': int(triggered[0]), 'b_triggered': int(triggered[1]), 'cat_inside': int(cat_inside)},
                                 separators=(',', ':'))

            msg_dict = dict={'Date':datetime.now(), 'A_triggered':int(triggered[0]), 'B_triggered':int(triggered[1]), 'cat_inside':cat_inside}

            # publish to topic
            detectCat.publish(message=msg, message_dict=msg_dict, topic=topic, connection=mqtt_connection, dt=dt)

            # Disconnect
            if disconnect:
                print("Disconnecting...")
                disconnect_future = mqtt_connection.disconnect()
                disconnect_future.result()
                break


