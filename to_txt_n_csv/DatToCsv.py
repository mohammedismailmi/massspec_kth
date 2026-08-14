import pandas as pd

def parse_pfeiffer_dat(file_path):
    # 1. Read the .dat file, skipping the first 8 lines of header metadata
    # The data is tab-separated (\t)
    df = pd.read_csv(file_path, sep='\t', skiprows=8)
    
    # 2. Keep only the columns we care about (Time, Pressure, and the Masses)
    columns_to_keep = [
        'Time Relative (sec)', 
        'Pressure_(mBar)', 
        '16_amu_(Methane)', 
        '18_amu_(Water)', 
        '28_amu_(Nitrogen)', 
        '32_amu_(Oxygen)', 
        '44_amu_(CO2)'
    ]
    df = df[columns_to_keep]
    
    # 3. "Melt" the dataframe. 
    # This turns the wide columns into flat rows (one row per mass per timestamp)
    df_melted = df.melt(
        id_vars=['Time Relative (sec)', 'Pressure_(mBar)'],
        value_vars=['16_amu_(Methane)', '18_amu_(Water)', '28_amu_(Nitrogen)', '32_amu_(Oxygen)', '44_amu_(CO2)'],
        var_name='Target_Mass',
        value_name='Raw_Signal_Amps'
    )
    
    # 4. Clean up the Target_Mass column to just be the integer (e.g., '16' instead of '16_amu_(Methane)')
    df_melted['mz'] = df_melted['Target_Mass'].str.extract(r'(\d+)').astype(int)
    df_melted = df_melted.drop('Target_Mass', axis=1)
    
    # 5. Inject the known constants for this specific run
    df_melted['True_Concentration_ppm'] = 100  # From the filename
    df_melted['Primary_Gas'] = 'Methane'
    
    return df_melted

# Run the function (replace with your actual file path)
pinn_dataset = parse_pfeiffer_dat("100PPMCH4-TR1, Position 1, RGA PrismaPro A 200 47505932, 002-11-2025 16'54'02.dat")

# Save to the final CSV for PyTorch
pinn_dataset.to_csv("PINN_Training_Data.csv", index=False)
print(pinn_dataset.head())