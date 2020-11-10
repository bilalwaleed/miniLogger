import busio
import digitalio
import board 
import threading
import time 
import ES2EEPROMUtils
import RPi.GPIO as GPIO
import adafruit_mcp3xxx.mcp3008 as MCP 
from adafruit_mcp3xxx.analog_in import AnalogIn 
import math
import datetime
import os

# some global variables that need to change as we run the program
sampling_time = 5
runtime = 0
presses = 0
end_logging = False #set if the user wants to end monitoring
buzzer_str = ' '
temp = 0
sysTime = datetime.datetime.now()  

#define pins
sampling_btn = 23
end_btn = 24
buzzer = 13
  
#setup 
def setup():
    #define board mode
    GPIO.setmode(GPIO.BCM)

    #setup buttons and buzzer
    GPIO.setup(sampling_btn, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(end_btn, GPIO.IN, pull_up_down = GPIO.PUD_UP)
    GPIO.setup(buzzer, GPIO.OUT)

    #add rising edge detection on a channel to debounce buttons 
    GPIO.add_event_detect(sampling_btn, GPIO.FALLING, callback=sampling_btn_pressed, bouncetime=400)
    GPIO.add_event_detect(end_btn, GPIO.FALLING, callback=end_btn_pressed, bouncetime=400)
    
    # Setup PWM channels
    global pwm_BUZ
    pwm_BUZ = GPIO.PWM(buzzer, 1000)

    pass

##SETTING UP ADC##
#create the spi bus
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
# create the cs (chip select)
cs = digitalio.DigitalInOut(board.D5)
# create the mcp object
mcp = MCP.MCP3008(spi, cs)
# create an analog input channel on pin 1
chan = AnalogIn(mcp, MCP.P1)

##SETTING UP EEPROM##
eeprom = ES2EEPROMUtils.ES2EEPROM()


def print_temp_thread():
    global runtime
    global temp
    global sysTime 
    #This function prints the temp to the screen as per sampling time 
    thread = threading.Timer(sampling_time, print_temp_thread)
    thread.daemon = True  # Daemon threads exit when the program does
    thread.start()
    if (not end_logging):
        adc_value = chan.value #adc opcode
        temp_voltage = chan.voltage #voltage from the adc
        temp = math.trunc((temp_voltage - 0.5)/0.01) #convert voltage into temp using equation from MCP9700 datasheet

        buz_sound(temp) #call buz_sound function  

        end = time.time() #get the end time 
        runtime = math.trunc(end-start) #calculate the runtime 
        sysTime = datetime.datetime.now()  #get the system time 
        sysTime_disp = sysTime.strftime("%H:%M:%S") #format system time to display hours,mins and seconds
        print('{:<12} {:<12s} {:<10s} {:<15s}'.format(sysTime_disp, str(runtime)+'s', str(temp) + ' C', buzzer_str))
    pass 


# sampling period button
def sampling_btn_pressed(sampling_btn):
#this function increases the sampling period if the button is pressed
    global sampling_time
    global presses
    presses+=1 #update presses 

    if (presses==1):
        sampling_time = 10 #chane sampling time
    elif (presses==2):
        sampling_time = 2 #change sampling time 
    elif (presses==3):
        sampling_time = 5 #change sampling time 
        presses=0 #loop back to 0 presses once the button has been pressed 3 times

pass

# stop/start monitoring
def end_btn_pressed(end_btn):
#this function stops/starts the monitoring if the button is pressed
    global end_logging
    if (end_logging==False): #check if end_logging flag is false
        pwm_BUZ.stop()
        os.system('clear')  
        print("Logging has stopped")
        end_logging = True
        option = input("Do you want to view the latest 20 readings? (Type 'y' to view readings)")
        option = option.upper()
        #call display function to print latest readings
        if option == "Y":
            os.system('clear')
            display_data()
            print(" ")
            print("Press the button to restart logging")
    else:
        #print heading
        os.system('clear')
        print('Logging restarted') #restart the logging 
        print('{:<12s} {:<12s} {:<10s} {:<15s}'.format('Time','Sys Timer', 'Temp', 'Buzzer'))
        end_logging = False #set end_logging flag to True

pass


#get the data stored in eeprom
def get_stored_data():
    #get the amount of readings logged
    readings_count = (eeprom.read_byte(0))

    #get the readings 
    temp_readings = []
    for i in range(1, readings_count+1):
        temp_readings.append((eeprom.read_block(i,4)))
    
    return readings_count, temp_readings
pass

#store latest data in eeprom
def store_latest_data():

    #This function stores the latest data 
    thread_data = threading.Timer(sampling_time, store_latest_data)
    thread_data.daemon = True  # Daemon threads exit when the program does
    thread_data.start()

    if not end_logging:
        count, readings = get_stored_data()
        #include new reading and update number of readings
        if (count<20):
            count+=1
        elif (count>=20):
            del readings[0]
    
        readings.append([sysTime.hour, sysTime.minute, sysTime.second, temp])

        #write new readings
        data_to_write = [count,0,0,0]
        for reading in readings:
        # get the string
            for i in range(0,4):
                data_to_write.append(reading[i])

        eeprom.write_block(0, data_to_write) #write to eeprom
pass 

#display latest data 
def display_data():
    count, readings = get_stored_data()
    # print the readinsg to the terminal in the correct format 
    print("Here are the latest readings:")
    print('{:<3s} {:<8s}     {:<10s}'.format('ID','Time', 'Temp'))
    # print out the readings in the required format
    loop_count = 0
    for i in range(count-1,-1,-1): #decrement loop to print data from newest to oldest
        loop_count+=1 #change id 
        print('{:<3d} {:<2s}:{:<2s}:{:<2s}     {:<10s}'.format(loop_count, str((readings[i][0])).zfill(2), str(readings[i][1]).zfill(2), str(readings[i][2]).zfill(2), str(readings[i][3]) + ' C'))
pass


#sound buzzer
def buz_sound(temp):
#this function sounds the buzzer if the temperature does not fall within a certain range
    global buzzer_str
    if (temp>29):
        pwm_BUZ.start(temp-29) #start buzzer with DC related to temp
        buzzer_str = '*' #change buzzer string 
    elif (temp<24):
        pwm_BUZ.start(24-temp) #start buzzer with DC related to temp
    else:
        pwm_BUZ.stop() #stop buzzer 
        buzzer_str = '' #change buzzer string
pass 

if __name__ == "__main__":
    try:
        setup() #call setup
        print('{:<12s} {:<12s} {:<10s} {:<15s}'.format('Time','Sys Timer', 'Temp', 'Buzzer'))
        start = time.time() #get the starting time of the thread
        print_temp_thread() #call function once to run
        store_latest_data()

        while runtime <3600: #stop system after 1 hour.
            pass
    except Exception as e:
        print(e)
    finally:
        GPIO.cleanup()

        
