"""
Copyright (c) 2023 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""

import paho.mqtt.client as mqtt
import meraki
import json
import datetime
import pytz
import config as config

# Create a Meraki Dashboard API client
dashboard = meraki.DashboardAPI(config.API_KEY)

# Initialize a counter for consecutive person detections
detection_counter = 0

# Initialize a variable for the timestamp of the first detection
first_detection_timestamp = None

# Callback function for MQTT connection
def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker with result code: " + str(rc))
    client.subscribe(config.topic)

def on_message(client, userdata, msg):
    global detection_counter, first_detection_timestamp  # Use the global variables

    try:
        # Parse the MQTT message payload as JSON
        payload = json.loads(msg.payload.decode())

        # Extract the timestamp from the MQTT message
        timestamp = payload.get('ts')

        # Extract the count of persons detected
        persons_detected = payload.get('counts', {}).get('person', 0)

        # Check if a person is detected
        if persons_detected > 0:
            detection_counter += 1
            # If it's the first detection, store the timestamp
            if detection_counter == 1:
                first_detection_timestamp = timestamp
        else:
            detection_counter = 0
            first_detection_timestamp = None  # Reset the timestamp

        print("Received MQTT message with", persons_detected, "person(s) detected.")

        # Check if the detection threshold is reached
        if detection_counter >= config.DETECTION_THRESHOLD:
            # Create a video link URL using the timestamp of the first detection
            video_link_url = create_video_link(first_detection_timestamp)

            if video_link_url:
                print("Created video link:", video_link_url)
            else:
                print("Failed to create video link.")

    except json.JSONDecodeError as e:
        print("Failed to decode MQTT message payload as JSON:", str(e))
    except Exception as e:
        print("Error:", str(e))

# Function to create a video link URL based on the provided timestamp
def create_video_link(timestamp=None):
    try:
        if timestamp:
            tz = dashboard.networks.getNetwork(networkId=config.NETWORK_ID)['timeZone']
            timestamp_str = epoch_to_iso8601(timestamp, tz)

            # Get the video link URL using the Meraki Dashboard SDK
            response = dashboard.camera.getDeviceCameraVideoLink(
                serial=config.CAMERA_SERIAL,
                timestamp=timestamp_str
            )

            # Extract the video link URL from the response
            video_link_url = response.get('url')

            # Append the video link URL to a JSON file
            append_video_link_to_json(timestamp_str, video_link_url)

            return video_link_url
        else:
            print("No timestamp provided.")
            return None
    except Exception as e:
        print("Failed to create video link. Error:", str(e))
        return None

# Function to append video link to a JSON file
def append_video_link_to_json(timestamp, video_link_url):
    try:
        json_data = {}  # Create an empty JSON object

        # Check if the JSON file exists
        try:
            with open('video_links.json', 'r') as json_file:
                json_data = json.load(json_file)
        except FileNotFoundError:
            pass

        # Append the video link URL to the JSON data
        json_data[timestamp] = video_link_url

        # Write the updated JSON data back to the file
        with open('video_links.json', 'w') as json_file:
            json.dump(json_data, json_file, indent=4)

        print("Appended video link to JSON file.")
    except Exception as e:
        print("Failed to append video link to JSON file. Error:", str(e))

def epoch_to_iso8601(epoch_timestamp, timezone_str):
    # Convert the epoch timestamp to seconds (assuming it's in milliseconds)
    timestamp_in_seconds = epoch_timestamp / 1000

    # Convert the timestamp to a datetime object
    dt = datetime.datetime.utcfromtimestamp(timestamp_in_seconds)

    # Set the timezone to UTC
    dt = dt.replace(tzinfo=pytz.utc)

    # Convert to the desired timezone
    target_timezone = pytz.timezone(timezone_str)
    localized_dt = dt.astimezone(target_timezone)

    # Format as ISO8601 without milliseconds
    return localized_dt.isoformat(timespec='seconds')

# Create MQTT client instance
client = mqtt.Client()

# Set callback functions
client.on_connect = on_connect
client.on_message = on_message

# Connect to MQTT broker
client.connect(config.broker_address, config.broker_port, 60)

# Start the MQTT network loop (blocking call)
client.loop_forever()