import serial
import csv
import time
from collections import deque

# Configure the serial port and baud rate to match your Arduino settings
ser = serial.Serial('COM6', 115200)  # Replace with your actual port and baud rate

# Define the duration for data collection in seconds
duration = 60  # Collect data for 30 seconds
buffer_time = 2  # Time in seconds to buffer before and after a throw
sampling_rate = 20  # Increase the sampling rate to 20 samples per second
buffer_size = int(buffer_time * sampling_rate)  # Buffer size based on the new sampling rate

# Open the CSV file for writing
csv_file_path = 'sensor_data.csv'
with open(csv_file_path, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['ThrowNumber', 'Time', 'SensorValue'])  # Write the header
    print(f"CSV file created at {csv_file_path}")

    start_time = time.time()
    throw_count = 0
    buffer = deque(maxlen=buffer_size * 2)  # Buffer to store data before and after a throw
    in_throw = False  # Flag to indicate if we are currently recording a throw
    post_throw_counter = 0  # Counter to track post-throw data points

    while (time.time() - start_time) < duration or in_throw:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()  # Ignore decoding errors
            if line:
                try:
                    timestamp, sensor_value = line.split(', ')
                    sensor_value = float(sensor_value)  # Convert sensor value to float for comparison
                    buffer.append((timestamp, sensor_value))  # Add data to buffer

                    if sensor_value > 2000 and not in_throw:  # Replace THROW_THRESHOLD with your actual threshold value
                        throw_count += 1
                        in_throw = True
                        post_throw_counter = buffer_size  # Reset post-throw counter
                        print(f"Throw detected at {timestamp}: {sensor_value}")  # Print the data to the console for debugging

                    if in_throw:
                        # Write buffered data to CSV
                        for buffered_timestamp, buffered_value in buffer:
                            writer.writerow([throw_count, buffered_timestamp, buffered_value])
                        buffer.clear()  # Clear buffer after writing

                        # Continue recording post-throw data
                        post_throw_counter -= 1
                        if post_throw_counter <= 0:
                            in_throw = False
                except ValueError:
                    # Handle the case where the line does not split into exactly 2 parts
                    print(f"Skipping malformed line: {line}")

# Close the serial connection
ser.close()
print(f"CSV file closed at {csv_file_path}")