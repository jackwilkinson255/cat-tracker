# Cat Tracker Data Engineering Project

<p align="center">
  <img src="cat.gif" alt="animated" width="400"/>
</p>

In this data engineering project we collect data from motion sensors to detect whether a cat is inside or
outside. Using AWS IoT we publish this data to a topic which is acted on by a rule which stores the message
data into a DynamoDB NoSQL table. 


## ETL Pipeline

### Extraction:
Data is extracted from an Arduino microcontroller connected to two passive infrared (PIR) sensors which detect motion. 
These are placed on either side of the cat flap we can then tell whether the cat is coming in or going out.
This data is sent from the Arduino to a Raspberry Pi via serial connection. 

### Transform:
The Raspberry Pi (running [main.py](main.py)) receives the status of the motion sensors. Knowing the order in which 
these motion sensors were triggered, we can detect if the is "inside" or "outside". We add a small delay to 
allow the cat to get through its flap before detecting a false reading. 

### Load: 
The data from the Raspberry Pi is then converted to json format and published through an MQTT connection
every 15 minutes. We then add a rule in IoT Core which scans for messages from a specified topic and then  
stores the device data into a DynamoDB table with a timestamp partition key.