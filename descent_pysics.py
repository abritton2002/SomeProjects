import pandas as pd
import pymysql
import numpy as np
from pybaseball import playerid_reverse_lookup
import matplotlib.pyplot as plt
from tqdm import tqdm

# Database connection details
#Had to remove for company policy


# Get player name input from the user
player_name = input("Enter the player name: ")

# Function to query the database and return a DataFrame with error handling
def query_database():
    query = """
    SELECT batter, description, plate_x, plate_z, sz_top, sz_bot,
           release_pos_x, release_pos_z, release_extension, vx0, vy0, vz0, ax, ay, az, game_date, events,
           hit_distance_sc, launch_speed
    FROM sc_raw
    WHERE YEAR(game_date) = 2024 AND description = 'hit_into_play'
    """  # SQL query to select specific columns from sc_raw table
    
    try:
        # Connect to the database
        connection = pymysql.connect(**db_config)
        with connection.cursor() as cursor:
            # Execute the query
            cursor.execute(query)
            # Fetch all the results
            result = cursor.fetchall()
            
            # Convert the result to a pandas DataFrame
            df = pd.DataFrame(result, columns=[
                'batter', 'description', 'plate_x', 'plate_z', 'sz_top', 'sz_bot',
                'release_pos_x', 'release_pos_z', 'release_extension', 'vx0', 'vy0', 'vz0', 'ax', 'ay', 'az', 'game_date', 'events',
                'hit_distance_sc', 'launch_speed'
            ])
            
            # Convert relevant columns to numeric values
            numeric_columns = ['plate_x', 'plate_z', 'sz_top', 'sz_bot',
                               'release_pos_x', 'release_pos_z', 'release_extension', 'vx0', 'vy0', 'vz0', 'ax', 'ay', 'az',
                               'hit_distance_sc', 'launch_speed']
            df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors='coerce')
            
            # Drop rows with any N/A values
            df.dropna(inplace=True)
            
            print("DataFrame after filtering and dropping N/A values:")
            print(df.head())  # Print the first 5 rows
            
            return df
    except pymysql.MySQLError as e:
        print(f"Error while connecting to the database: {e}")
        return pd.DataFrame()  # Return an empty DataFrame in case of error
    finally:
        if 'connection' in locals():
            connection.close()

# Query the database
data = query_database()

# Perform player ID lookup to get batter names
batter_ids = data['batter'].unique()
batter_names = playerid_reverse_lookup(batter_ids, key_type='mlbam')
batter_names_dict = dict(zip(batter_names['key_mlbam'], batter_names['name_first'] + ' ' + batter_names['name_last']))

# Map batter IDs to names
data['batter_name'] = data['batter'].map(batter_names_dict)

# Filter data for the specified player
player_data = data[data['batter_name'] == player_name]

# Remove rows with event 'catcher_interf'
data = data[data['events'] != 'catcher_interf']
player_data = player_data[player_data['events'] != 'catcher_interf']

# Check if there are at least 100 event instances for the player
if player_data.shape[0] < 100:
    print(f"Not enough data for player: {player_name}. Found only {player_data.shape[0]} instances.")
else:
    # Function to calculate the position of the pitch at time t
    def calculate_position(release_pos_x, release_pos_z, release_extension, vx0, vy0, vz0, ax, ay, az, t):
        x = (release_pos_x + vx0 * t + 0.5 * ax * t**2)
        y = (60.5 - release_extension + vy0 * t + 0.5 * ay * t**2)  # Reflecting along y = 0
        z = release_pos_z + vz0 * t + 0.5 * az * t**2
        return x, y, z

    # Function to calculate the descent angle for a single pitch
    def calculate_descent_angle(release_pos_x, release_pos_z, release_extension, vx0, vy0, vz0, ax, ay, az):
        time_steps = 1000
        time = np.linspace(0, 1, time_steps)
        positions = np.array([calculate_position(release_pos_x, release_pos_z, release_extension, 
                                                 vx0, vy0, vz0, ax, ay, az, t) for t in time])
        plate_y = 0
        crossing_index = np.argmin(np.abs(positions[:, 1] - plate_y))
        positions = positions[:crossing_index + 1]
        dx = positions[-1, 0] - positions[-2, 0]
        dy = positions[-1, 1] - positions[-2, 1]
        dz = positions[-1, 2] - positions[-2, 2]
        descent_angle_plate = np.arctan2(dz, np.sqrt(dx**2 + dy**2))
        return np.degrees(descent_angle_plate)

    # Calculate descent angles for all pitches with a progress meter
    descent_angles = []
    events = []

    for _, row in tqdm(data.iterrows(), total=data.shape[0]):
        angle = calculate_descent_angle(row['release_pos_x'], row['release_pos_z'], 
                                        row['release_extension'], row['vx0'], row['vy0'], 
                                        row['vz0'], row['ax'], row['ay'], row['az'])
        descent_angles.append(angle)
        events.append(row['events'])

    data.loc[:, 'descent_angle'] = descent_angles
    data.loc[:, 'event'] = events

    # Calculate descent angles for the specified player
    player_descent_angles = []
    player_events = []

    for _, row in tqdm(player_data.iterrows(), total=player_data.shape[0]):
        angle = calculate_descent_angle(row['release_pos_x'], row['release_pos_z'], 
                                        row['release_extension'], row['vx0'], row['vy0'], 
                                        row['vz0'], row['ax'], row['ay'], row['az'])
        player_descent_angles.append(angle)
        player_events.append(row['events'])

    player_data.loc[:, 'descent_angle'] = player_descent_angles
    player_data.loc[:, 'event'] = player_events

    # Group specific events into 'field_out'
    field_out_events = ['grounded_into_double_play', 'error', 'double_play', 'force_out', 'field_error', 'fielders_choice_out', 'fielders_choice']
    data.loc[data['event'].isin(field_out_events), 'event'] = 'field_out'
    player_data.loc[player_data['event'].isin(field_out_events), 'event'] = 'field_out'

    # Bin the descent angles into 1-degree groups
    data.loc[:, 'descent_angle_bin'] = np.floor(data['descent_angle'])
    player_data.loc[:, 'descent_angle_bin'] = np.floor(player_data['descent_angle'])

    # Group by descent angle bin and calculate success metrics for the entire dataset
    grouped = data.groupby('descent_angle_bin').agg({
        'event': lambda x: x.value_counts(normalize=True).to_dict(),
        'hit_distance_sc': 'mean',
        'launch_speed': 'mean'
    }).reset_index()

    # Add event count to the grouped DataFrame
    grouped['event_count'] = data.groupby('descent_angle_bin').size().values

    # Filter out bins with fewer than 10 events
    grouped = grouped[grouped['event_count'] >= 10]

    # Group by descent angle bin and calculate success metrics for the player
    player_grouped = player_data.groupby('descent_angle_bin').agg({
        'event': lambda x: x.value_counts(normalize=True).to_dict(),
        'hit_distance_sc': 'mean',
        'launch_speed': 'mean'
    }).reset_index()

    # Add event count to the player grouped DataFrame
    player_grouped['event_count'] = player_data.groupby('descent_angle_bin').size().values

    # Filter out bins with fewer than 10 events for the player
    player_grouped = player_grouped[player_grouped['event_count'] >= 10]

    # ... existing code ...
# ... existing code ...

# Remove rows with event 'sac_fly'
data = data[data['events'] != 'sac_fly']
player_data = player_data[player_data['events'] != 'sac_fly']
# ... existing code ...
# ... existing code ...

# Function to create a radar (spider) plot
def create_radar_chart(bin_data, player_bin_data, bin_label, player_name):
    # Define the events to be included in the radar plot
    included_events = ['field_out', 'single', 'double', 'triple', 'home_run']
    
    # Filter the bin_data and player_bin_data to include only the specified events
    bin_data = {event: bin_data.get(event, 0) for event in included_events}
    player_bin_data = {event: player_bin_data.get(event, 0) for event in included_events}
    
    # Number of variables we're plotting (one per event)
    categories = list(bin_data.keys())
    num_vars = len(categories)
    
    # Split the circle into even parts and save the angles
    # so we know where to put each axis
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()

    # The radar chart is circular, so we need to "complete the loop"
    # and append the start angle to the end
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    
    # Draw one axe per variable + add labels
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    
    plt.xticks(angles[:-1], categories)
    
    # Draw ylabels
    ax.set_ylim(0, 0.8)
    
    # Values for the bin we're plotting
    values = [bin_data.get(event, 0) for event in categories]
    values += values[:1]
    
    # Values for the player bin we're plotting
    player_values = [player_bin_data.get(event, 0) for event in categories]
    player_values += player_values[:1]
    
    # Plot data
    ax.plot(angles, values, linewidth=1, linestyle='solid', label='Overall')
    ax.fill(angles, values, alpha=0.25)

    # Plot player data
    ax.plot(angles, player_values, linewidth=1, linestyle='solid', color='red', label=player_name)
    ax.fill(angles, player_values, alpha=0.25, color='red')
    
    plt.title(f"Radar Plot for '{player_name}': Descent Angle Bin {bin_label}", size=15, color='blue', y=1.1)
    plt.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))

    plt.show()

# Create radar plots for each descent angle bin
for _, row in grouped.iterrows():
    player_row = player_grouped[player_grouped['descent_angle_bin'] == row['descent_angle_bin']]
    if not player_row.empty:
        create_radar_chart(row['event'], player_row.iloc[0]['event'], row['descent_angle_bin'], player_name)