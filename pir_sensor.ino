// Short Arduino script for communicating with sensors

int pirPin_in = 4;              // PIR Out pin
int pirPin_out = 7; 
int pirStat_in = 0;             // PIR status
int pirStat_out = 0;
int count = 0;

void setup() {
 pinMode(pirPin_in, INPUT);
 pinMode(pirPin_out, INPUT);  
 Serial.begin(115200);
}

void loop(){
  pirStat_in = digitalRead(pirPin_in); 
  pirStat_out = digitalRead(pirPin_out);
  Serial.print(pirStat_in);
  Serial.print(" ");
  Serial.println(pirStat_out);
} 
