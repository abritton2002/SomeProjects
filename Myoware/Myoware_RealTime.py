import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import csv
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Constants
SERIAL_PORT = 'COM6'
BAUD_RATE = 115200

# Initialize serial connection
ser = serial.Serial(SERIAL_PORT, BAUD_RATE)

# Initialize empty lists to store data
x_vals = []
sensorValue1_data = []
sensorValue2_data = []

# Create a function to read and process data from Arduino
def read_and_process_data():
    line = ser.readline().decode('utf-8').strip()
    sensorValues = line.split(', ')

    if len(sensorValues) != 3:
        print(f"Unexpected data format: {line}")
        return

    try:
        x_vals.append(float(sensorValues[0]))
        sensorValue1_data.append(int(sensorValues[1]))
        sensorValue2_data.append(int(sensorValues[2]))

        # Print the received values
        print(f'Time: {sensorValues[0]}, Sensor 1: {sensorValues[1]}, Sensor 2: {sensorValues[2]}')
    except ValueError as e:
        print(f"Error processing line: {line} | Error: {e}")

# Create a function to update the plot
def update_plot(frame):
    read_and_process_data()
    if len(x_vals) == len(sensorValue1_data) == len(sensorValue2_data):  # Ensure all lists have the same length
        ax.cla()
        ax.plot(x_vals, sensorValue1_data, label='Sensor 1')
        ax.plot(x_vals, sensorValue2_data, label='Sensor 2')
        ax.set_xlabel('Time')
        ax.set_ylabel('Sensor Values')
        ax.legend()
        canvas.draw()

# Create a function to save data to a CSV file when the plot window is closed
def on_close(event):
    with open('arduino_data.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Time', 'Sensor1', 'Sensor2'])
        for x, s1, s2 in zip(x_vals, sensorValue1_data, sensorValue2_data):
            writer.writerow([x, s1, s2])
    ser.close()
    root.quit()

# Initialize Tkinter root
root = tk.Tk()
root.title("Sensor Data Real-Time Plot")

# Create a matplotlib figure and axis
fig, ax = plt.subplots()
canvas = FigureCanvasTkAgg(fig, master=root)
canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

# Register the callback function
fig.canvas.mpl_connect('close_event', on_close)
ani = FuncAnimation(fig, update_plot, interval=1000)  # Update every second

# Start the Tkinter main loop
root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()