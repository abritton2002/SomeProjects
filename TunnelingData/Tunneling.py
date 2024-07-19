import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
# import pymysql  # Remove this import if no longer needed

# Database connection details
# db_config = {
#     'host': '10.200.200.107',
#     'user': 'readonlyuser',
#     'password': 'pKufhAALb7r9Z0x',
#     'database': 'statcast_db'
# }

# Connect to the database
# connection = pymysql.connect(**db_config)

# Query to fetch data from the table starting from April 1st, 2024
# query = """
# SELECT * 
# FROM sc_raw 
# WHERE game_date >= '2024-04-01'
# """
# ... existing code ...
data = pd.read_csv(r'C:\Users\alex.britton\Documents\Cursor\Python\Statcast_Pull\statcast_data_daily.csv')  # Update with the correct path to your CSV file

# Close the database connection
# connection.close()

# Debug: Print the number of unique pitchers in the original dataset
print(f"Number of unique pitchers in the original dataset: {data['player_name'].nunique()}")

# Function to calculate the position of the pitch at time t
def calculate_position(release_pos_x, release_pos_z, release_extension, vx0, vy0, vz0, ax, ay, az, t):
    x = release_pos_x + vx0 * t + 0.5 * ax * t**2
    y = (60.5 - release_extension) + (vy0 * t + 0.5 * ay * t**2)  # Adjust y to start from 60.5 - release_extension
    z = release_pos_z + vz0 * t + 0.5 * az * t**2
    return x, y, z

# Calculate the trajectory for each pitch at different time points
time_points = np.linspace(0, 0.5, 100)  # Time points from 0 to 0.5 seconds
trajectories = []

for index, row in data.iterrows():
    trajectory = [calculate_position(row['release_pos_x'], row['release_pos_z'], row['release_extension'], row['vx0'], row['vy0'], row['vz0'], row['ax'], row['ay'], row['az'], t) for t in time_points]
    trajectories.append(trajectory)

data['trajectory'] = trajectories

# Calculate the average trajectory for each pitch type for each pitcher
average_trajectories = data.groupby(['player_name', 'pitch_type'])['trajectory'].apply(lambda x: np.mean(np.array(x.tolist()), axis=0))

# Function to find the tunnel point between a pitch and the average fastball trajectory
def find_tunnel_point(trajectory, average_fastball_trajectory, distance_threshold=0.25):
    for i in range(len(trajectory)):
        distance = np.sqrt((trajectory[i][0] - average_fastball_trajectory[i][0])**2 + 
                           (trajectory[i][2] - average_fastball_trajectory[i][2])**2)  # x and z coordinates
        if distance >= distance_threshold:  # Distance threshold
            return trajectory[i][1]  # Return distance from home plate (y-coordinate)
    return None

# Drop rows with NaN values in the 'pitch_type' column
data = data.dropna(subset=['pitch_type'])

# Calculate the average tunnel distance for each pitcher
tunnel_distances = []

for player_name, group in data.groupby('player_name'):
    fastball_trajectory = average_trajectories[player_name, 'FF'] if ('FF' in average_trajectories[player_name]) else None
    if fastball_trajectory is not None:
        distances = []
        for pitch_type in group['pitch_type'].unique():
            if pitch_type != 'FF':
                pitch_trajectory = average_trajectories.get((player_name, pitch_type))
                if pitch_trajectory is not None:
                    tunnel_distance = find_tunnel_point(pitch_trajectory, fastball_trajectory)
                    if tunnel_distance is not None:
                        distances.append(tunnel_distance)
        if distances:
            average_tunnel_distance = np.mean(distances)
            tunnel_distances.append((player_name, average_tunnel_distance))

# Create a DataFrame for the tunnel distances
tunnel_distances_df = pd.DataFrame(tunnel_distances, columns=['player_name', 'average_tunnel_distance'])

# Drop rows with NaN values in the average_tunnel_distance column
tunnel_distances_df = tunnel_distances_df.dropna(subset=['average_tunnel_distance'])

# Normalize the TNL metric so that the highest score is 100
max_tunnel_distance = tunnel_distances_df['average_tunnel_distance'].max()
tunnel_distances_df['TNL'] = ((max_tunnel_distance - tunnel_distances_df['average_tunnel_distance']) / max_tunnel_distance * 100).astype(int)

# Sort the pitchers by TNL metric in descending order
tunnel_distances_df = tunnel_distances_df.sort_values(by='TNL', ascending=False)

# Display the top 20 pitchers by TNL metric
top_20_pitchers = tunnel_distances_df.head(20)
print("\nTop 20 pitchers by TNL metric:")
print(top_20_pitchers)

# Visualization: Plot average trajectories for the top 20 pitchers
plt.figure(figsize=(12, 6))
for player_name in top_20_pitchers['player_name']:
    for pitch_type, trajectory in average_trajectories[player_name].items():
        x = [pos[0] for pos in trajectory]
        y = [pos[1] for pos in trajectory]
        z = [pos[2] for pos in trajectory]
        plt.plot(y, z, label=f"{player_name} - {pitch_type}")

plt.xlabel('Distance from Home Plate (feet)')
plt.ylabel('Vertical Position (feet)')
plt.title('Average Pitch Trajectories of the Top 20 Pitchers by TNL')
plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
plt.show()

# Visualization: Plot average tunnel distances for the top 20 pitchers
plt.figure(figsize=(12, 6))
plt.barh(top_20_pitchers['player_name'], top_20_pitchers['average_tunnel_distance'], color='skyblue')
plt.xlabel('Average Tunnel Distance (feet)')
plt.ylabel('Pitcher')
plt.title('Average Tunnel Distances for the Top 20 Pitchers by TNL')
plt.gca().invert_yaxis()
plt.show()

# Create a linear regression model to predict TNL score based on tunnel distance
X = tunnel_distances_df[['average_tunnel_distance']]
y = tunnel_distances_df['TNL']

model = LinearRegression()
model.fit(X, y)

# Predict TNL scores
tunnel_distances_df['predicted_TNL'] = model.predict(X)

# Define percentiles for categories
percentiles = pd.qcut(tunnel_distances_df['predicted_TNL'], q=[0, 0.1, 0.25, 0.75, 1.0], labels=['Below Average', 'Average', 'Above Average', 'Elite'])

# Apply the categorization
tunnel_distances_df['Category'] = percentiles

# Display the DataFrame with predicted TNL scores and categories
print("\nDataFrame with Predicted TNL Scores and Categories:")
print(tunnel_distances_df)

# Define the directory to save the output file
data_dir = r'C:\Users\alex.britton\Documents\Cursor\Python\Tunneling'  # Ensure this directory exists or create it
output_file_path = os.path.join(data_dir, 'tunnel_distances.csv')

# Save the DataFrame to a CSV file
tunnel_distances_df.to_csv(output_file_path, index=False)
print(f"\nDataFrame written to {output_file_path}")

# Visualization: Plot actual vs predicted TNL scores
plt.figure(figsize=(12, 6))
plt.scatter(tunnel_distances_df['average_tunnel_distance'], tunnel_distances_df['TNL'], color='blue', label='Actual TNL')
plt.plot(tunnel_distances_df['average_tunnel_distance'], tunnel_distances_df['predicted_TNL'], color='red', label='Predicted TNL')
plt.xlabel('Average Tunnel Distance (feet)')
plt.ylabel('TNL Score')
plt.title('Actual vs Predicted TNL Scores')
plt.legend()
plt.show()

# Visualization: Plot TNL categories
plt.figure(figsize=(12, 6))
category_counts = tunnel_distances_df['Category'].value_counts()
plt.bar(category_counts.index, category_counts.values, color=['gray', (205/255, 127/255, 50/255), 'silver', 'gold'])
plt.xlabel('Category')
plt.ylabel('Number of Pitchers')
plt.title('Distribution of Pitchers by TNL Category')
plt.show()