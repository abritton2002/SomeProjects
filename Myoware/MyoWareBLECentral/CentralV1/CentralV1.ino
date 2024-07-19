#include <ArduinoBLE.h>
#include <MyoWare.h>
#include <vector>

// debug parameters
const bool debugLogging = false; // set to true for verbose logging to serial

std::vector<BLEDevice> vecMyoWareShields;

// MyoWare class object
MyoWare myoware;

// Variables for storing muscle voltage data
const int bufferSize = 460;  // 0.5 seconds before and 0.5 seconds after at 1000 Hz sampling rate
int muscleVoltageBuffer[bufferSize];
int bufferIndex = 0;
bool throwDetected = false;
unsigned long throwStartTime = 0;

void setup() {
  Serial.begin(115200);
  while (!Serial);

  pinMode(myoware.getStatusLEDPin(), OUTPUT); // initialize the built-in LED pin to indicate 
                                              // when a central is connected

  // begin initialization
  if (!BLE.begin()) {
    Serial.println("Starting BLE failed!");
    while (1);
  }

  if (debugLogging) {
    Serial.println("MyoWare BLE Central");
    Serial.println("-------------------");
  }

  // start scanning for MyoWare Wireless Shields
  if (debugLogging) {
    Serial.print("Scanning for MyoWare Wireless Shields: ");
    Serial.println(MyoWareBLE::uuidMyoWareService.c_str());
  }

  BLE.scanForUuid(MyoWareBLE::uuidMyoWareService.c_str(), true);

  // scan for Wireless Shields for 10sec
  const long startMillis = millis();
  while (millis() - startMillis < 10000) {
    myoware.blinkStatusLED();

    BLEDevice peripheral = BLE.available();
    if (peripheral && std::find(vecMyoWareShields.begin(), vecMyoWareShields.end(), peripheral) == vecMyoWareShields.end()) {
      if (debugLogging) {
        Serial.print("Connecting to ");
        PrintPeripheralInfo(peripheral);
      }

      // connect to the peripheral
      BLE.stopScan();
      if (peripheral.connect()) {
        if (!peripheral.discoverAttributes()) {
          Serial.println("Discovering Attributes... Failed!");
          if (!peripheral.discoverAttributes()) {
            Serial.println("Discovering Attributes... Failed!");
            Serial.print("Disconnecting... ");
            PrintPeripheralInfo(peripheral);
            peripheral.disconnect();
            Serial.println("Disconnected");
            continue;
          }
        }
        vecMyoWareShields.push_back(peripheral);
      } else {
        Serial.print("Failed to connect: ");        
        PrintPeripheralInfo(peripheral);
      }
      BLE.scanForUuid(MyoWareBLE::uuidMyoWareService.c_str(), true);
    }
  }
  BLE.stopScan();

  if (vecMyoWareShields.empty()) {
    Serial.println("No MyoWare Wireless Shields found!");
    while (1);
  }  
    
  digitalWrite(myoware.getStatusLEDPin(), HIGH); // turn on the LED to indicate a connection

  for (auto shield : vecMyoWareShields) {
    auto ritr = vecMyoWareShields.rbegin();
    if (ritr != vecMyoWareShields.rend() && shield != (*ritr)) {
      Serial.print(shield.localName());
      Serial.print("\t");
    } else {
      Serial.println(shield.localName());
    }
  }
}

void loop() {  
  for (auto shield : vecMyoWareShields) {
    if (!shield) {
      auto itr = std::find(vecMyoWareShields.begin(), vecMyoWareShields.end(), shield);
      if (itr != vecMyoWareShields.end())
        vecMyoWareShields.erase(itr);
      continue;
    }

    if (debugLogging) {
      Serial.print("Updating ");
      PrintPeripheralInfo(shield);
    }

    if (!shield.connected()) {
      continue;
    }

    BLEService myoWareService = shield.service(MyoWareBLE::uuidMyoWareService.c_str());
    if (!myoWareService) {
      shield.disconnect();
      continue;
    }
    
    // get sensor data
    BLECharacteristic sensorCharacteristic = myoWareService.characteristic(MyoWareBLE::uuidMyoWareCharacteristic.c_str());

    const double sensorValue = ReadBLEData(sensorCharacteristic);
    int muscleVoltage = sensorValue;  // assuming sensorValue gives the muscle voltage
    muscleVoltageBuffer[bufferIndex] = muscleVoltage;
    bufferIndex = (bufferIndex + 1) % bufferSize;

    // Detect throw
    if (muscleVoltage > 1000) {
      if (!throwDetected) {
        throwDetected = true;
        throwStartTime = millis();
      }
    }

    // Check if we need to output the throw data
    if (throwDetected && (millis() - throwStartTime >= 1000)) {
      outputThrowData();
      throwDetected = false;
    }
  }
}

// Read the sensor values from the characteristic
double ReadBLEData(BLECharacteristic& dataCharacteristic) {
  if (dataCharacteristic) {
    if (dataCharacteristic.canRead()) {
      // read the characteristic value as string
      char characteristicValue[20];
      dataCharacteristic.readValue(&characteristicValue, 20);
      const String characteristicString(characteristicValue); 

      return characteristicString.toDouble();
    } else {
      if (debugLogging) {
        Serial.print("Unable to read characteristic: ");
        Serial.println(dataCharacteristic.uuid());
      }
      return 0.0;
    }
  } else {
    if (debugLogging)
      Serial.println("Characteristic not found!");
  }
  return 0.0;
}

void PrintPeripheralInfo(BLEDevice peripheral) {
  Serial.print(peripheral.address());
  Serial.print(" '");
  Serial.print(peripheral.localName());
  Serial.print("' ");
  Serial.println(peripheral.advertisedServiceUuid());
}

void outputThrowData() {
  Serial.println("Throw detected:");
  int startIndex = (bufferIndex + bufferSize - 500) % bufferSize;
  for (int i = 0; i < 1000; i++) {
    int index = (startIndex + i) % bufferSize;
    Serial.println(muscleVoltageBuffer[index]);
  }
}
