# QN Scale BLE

This package is a fork of https://github.com/ronnnnnnnnnnnnn/etekcity_esf551_ble that has been modified to connect to the FITINDEX ES-26M Bluetooth smart scale, internally named "QN-Scale". The modifications were based on the reverse engineering work and code in the [OpenScale project](https://github.com/oliexdev/openScale).

## Installation

Install the package using pip:

```bash
pip install qn_scale_ble
```


## Quick Start

Here's a basic example of how to use the library:

```python
import asyncio
from qn_scale_ble import (
    IMPEDANCE_KEY,
    WEIGHT_KEY,
    QnScale,
    ScaleData,
    WeightUnit,
    BodyMetrics,
    Sex,
)

async def main():
    def notification_callback(data: ScaleData):
        print(f"Weight: {data.measurements[WEIGHT_KEY]} kg")
        print(f"Display Unit: {data.display_unit.name}")
        if IMPEDANCE_KEY in data.measurements:
            print(f"Impedance: {data.measurements[IMPEDANCE_KEY]} Ω")
            
            # Calculate body metrics
            # Note: Replace with your actual height, age and sex
            body_metrics = BodyMetrics(
                weight_kg=data.measurements[WEIGHT_KEY],
                height_m=1.75,  # Example height
                age=30,  # Example age
                sex=Sex.Male,  # Example sex
                impedance=data.measurements[IMPEDANCE_KEY]
            )
            print(f"Body Mass Index: {body_metrics.body_mass_index:.2f}")
            print(f"Body Fat Percentage: {body_metrics.body_fat_percentage:.1f}%")
            print(f"Fat-Free Weight: {body_metrics.fat_free_weight:.2f} kg")
            print(f"Subcutaneous Fat Percentage: {body_metrics.subcutaneous_fat_percentage:.1f}%")
            print(f"Visceral Fat Value: {body_metrics.visceral_fat_value}")
            print(f"Body Water Percentage: {body_metrics.body_water_percentage:.1f}%")
            print(f"Basal Metabolic Rate: {body_metrics.basal_metabolic_rate} calories")
            print(f"Skeletal Muscle Percentage: {body_metrics.skeletal_muscle_percentage:.1f}%")
            print(f"Muscle Mass: {body_metrics.muscle_mass:.2f} kg")
            print(f"Bone Mass: {body_metrics.bone_mass:.2f} kg")
            print(f"Protein Percentage: {body_metrics.protein_percentage:.1f}%")
            print(f"Metabolic Age: {body_metrics.metabolic_age} years")

    # Replace XX:XX:XX:XX:XX:XX with your scale's Bluetooth address
    scale = QnScale("XX:XX:XX:XX:XX:XX", notification_callback)
    scale.display_unit = WeightUnit.KG  # Set display unit to kilograms

    await scale.async_start()
    await asyncio.sleep(30)  # Wait for measurements
    await scale.async_stop()

asyncio.run(main())
```
For a real-life usage example of this library, check out the [Etekcity Fitness Scale BLE Integration for Home Assistant](https://github.com/ronnnnnnnnnnnnn/etekcity_fitness_scale_ble).


## API Reference

### `QnScale`

The main class for interacting with the scale.

#### Methods:

- `__init__(self, address: str, notification_callback: Callable[[ScaleData], None], display_unit: WeightUnit = None)`
- `async_start()`: Start scanning for and connecting to the scale.
- `async_stop()`: Stop the connection to the scale.

#### Properties:

- `display_unit`: Get or set the display unit (WeightUnit.KG, WeightUnit.LB or WeightUnit.ST). Returns None if the display unit is currently unknown (not set by the user and not yet received from the scale together with a stable weight measurement).
- `hw_version`: Get the hardware version of the scale (read-only).
- `sw_version`: Get the software version of the scale (read-only).

### `QnScaleWithBodyMetrics`

An extended version of QnScale that automatically calculates body metrics.

#### Methods:

- `__init__(self, address: str, notification_callback: Callable[[ScaleData], None], sex: Sex, birthdate: date, height_m: float, display_unit: WeightUnit = None)`
- `async_start()`: Start scanning for and connecting to the scale.
- `async_stop()`: Stop the connection to the scale.

#### Properties:

- `display_unit`: Get or set the display unit (WeightUnit.KG, WeightUnit.LB or WeightUnit.ST). Returns None if the display unit is currently unknown (not set by the user and not yet received from the scale together with a stable weight measurement).
- `hw_version`: Get the hardware version of the scale (read-only).
- `sw_version`: Get the software version of the scale (read-only).

### `WeightUnit`

An enum representing the possible display units:

- `WeightUnit.KG`: Kilograms
- `WeightUnit.LB`: Pounds
- `WeightUnit.ST`: Stones

### `ScaleData`

A dataclass containing scale measurement data:

- `name`: Scale name
- `address`: Scale Bluetooth address
- `hw_version`: Hardware version
- `sw_version`: Software version
- `display_unit`: Current display unit (concerns only the weight as displayed on the scale, the measurement itself is always provided by the API in kilograms)
- `measurements`: Dictionary of measurements (currently supports: weight in kilograms and impedance in ohms)

### `BodyMetrics`

A class for calculating various body composition metrics based on height, age, sex, and the weight and impedance as measured by the scale, similar to the metrics calculated and shown in the VeSync app. Note that currently "Athlete Mode" is not supported.

#### Methods:

- `__init__(self, weight_kg: float, height_m: float, age: int, sex: Sex, impedance: int)`

#### Properties:

- `body_mass_index`: Body Mass Index (BMI)
- `body_fat_percentage`: Estimated body fat percentage
- `fat_free_weight`: Weight of non-fat body mass in kg
- `subcutaneous_fat_percentage`: Estimated subcutaneous fat percentage
- `visceral_fat_value`: Estimated visceral fat level (unitless)
- `body_water_percentage`: Estimated body water percentage
- `basal_metabolic_rate`: Estimated basal metabolic rate in calories
- `skeletal_muscle_percentage`: Estimated skeletal muscle percentage
- `muscle_mass`: Estimated muscle mass in kg
- `bone_mass`: Estimated bone mass in kg
- `protein_percentage`: Estimated protein percentage
- `weight_score`: Calculated weight score (0-100)
- `fat_score`: Calculated fat score (0-100)
- `bmi_score`: Calculated BMI score (0-100)
- `health_score`: Overall health score based on other metrics (0-100)
- `metabolic_age`: Estimated metabolic age in years

### `Sex`

An enum representing biological sex for body composition calculations:

- `Sex.Male`
- `Sex.Female`


## Compatibility

- Tested on Mac (Apple Silicon) and Raspberry Pi 4
- Compatibility with Windows is unknown


## Troubleshooting

On Raspberry Pi 4 (and possibly other Linux machines using BlueZ), if you encounter a `org.bluez.Error.InProgress` error, try the following in `bluetoothctl`:

```
power off
power on
scan on
```
(See https://github.com/home-assistant/core/issues/76186#issuecomment-1204954485)


## Support the Project

If you find this unofficial project helpful, consider buying the upstream project author(s) a coffee!

etekcity_esf551_ble: [![Buy Me A Coffee](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/ronnnnnnn)

OpenScale: [Donations](https://github.com/oliexdev/openScale?tab=readme-ov-file#donations-heart)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


## Disclaimer

This is an independent project developed by the community. It is not endorsed by, directly affiliated with, maintained, authorized, or sponsored by the scale manufacturers or any of their affiliates or subsidiaries. All product and company names are the registered trademarks of their original owners. The use of any trade name or trademark is for identification and reference purposes only and does not imply any association with the trademark holder of their product brand.
