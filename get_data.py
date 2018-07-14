import pandas as pd
import pyaudio
import numpy as np
import os
from sklearn.preprocessing import normalize
import datetime
import threading
import time
import queue
from pynput import keyboard

pa = pyaudio.PyAudio()
print(pa.get_default_input_device_info())


import threading
import time
import queue

class KeyAudio(object):
    def __init__(self):
        print("Instantiating...")
        
        # I want to record for approximately 250ms for each keypress. This recording should center on the press event.
        # <---200ms---> KeyRelease <---50ms--->
        
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.delta_ms = 25 # Stream read size in milliseconds
        self.full_record_ms = 250 # Key press audio recording length in milliseconds
        self.post_rel_ms = 50 # Recording time after key release in milliseconds
        
        self.row_size = int(self.rate / self.chunk * self.delta_ms * (1/1000))
        
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format = self.format, channels = self.channels, rate = self.rate, input = True, frames_per_buffer = self.chunk)
        
        self.saving = False # Saving dataframe flag
        self.running = False # Keyboard and Audio Log started flag
        self.released = True
        self.start_time = 0.0 # Time key pressed
        self.max_hold_ms = 500 # Maximum time between hold and release for recording to be valid
        
        self.frames = [] # A list of delta_ms raw byte samples
        self.df_list = [] # Holds list of dictionaries until user saves as dataframe
        self.q = queue.Queue() # Use Queue as FIFO for recorded frames
        
        self.key_cnt = 0 # Track the number of recorded keypresses for this session
        
        self.dataset_subdir = 'DataSet/'
        self.save_cnt = 0
    
    # Start Listening for Keyboard Presses and recording Audio
    def startListener(self):
        print("Starting listener...")
        self.running = True
        
        # Record microphone in separate thread
        threads = []
        t = threading.Thread(target=self.log)
        threads.append(t)
        t.start()

        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
            listener.join()
      
    # Keyboard Press
    def on_press(self, key):
        if self.released == True:
            self.start_time = time.time()
            
            self.released = False
            
    def on_release(self, key):
        self.released = True
        
        # Escape Pressed
        if key == keyboard.Key.esc:
            self.running = False
            return False # Stop Key Listener
        else:
            # Time between press and release should be less than some delta threshold
            if time.time() - self.start_time > self.max_hold_ms/1000:
                return
            # Don't record data when saving
            if self.saving:
                return
            
            print(key)
            
            time.sleep(self.post_rel_ms/1000) # Keep recording audio for some delta defined after the key is pressed
            
            if self.q.qsize() != round(self.full_record_ms/self.delta_ms):
                print("Error: Incorrect queue size: {}".format(self.q.qsize()))
                return
            
            self.frames = list(self.q.queue)
            frame_bytes = bytearray([byte for row in self.frames for byte in row])
            frames_int = np.frombuffer(frame_bytes, dtype=np.int16) # convert to int16
            
            # Create dictionary for each sample and append to list (used later to create dataframe)
            record_sample = [{'key': self.key_to_string(key), 'data': frames_int, 'raw': frame_bytes, 'timestamp': datetime.datetime.utcnow()}]
            self.df_list.extend(record_sample)
            
            # Save data to dataframe
            if self.key_cnt % 500 == 499:
                print("Saving dataframe. Session key count: {}".format(self.key_cnt))
                filename = self.dataset_subdir + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + '_' + str(self.save_cnt) + '.pkl'
                self.save_dataframe(filename=filename)
            
            self.key_cnt += 1 # New keypress recorded
            
    def key_to_string(self, key):
        key_str = ""
        if str(type(key)) == "<enum 'Key'>":
            key_str = key.name # Type <enum 'Key'
        else:
            key_str = key.char # Type pynput.keyboard._win32.KeyCode
        return key_str
            
    def log(self):
        while self.running:
            data = self.stream.read(self.chunk * self.row_size) # Raw data in byte format
            self.q.put(data)

            if self.q.qsize() > round(self.full_record_ms/self.delta_ms):
                self.q.get()

        # When run complete, stop stream
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
    
    def save_data_as_wav(self, data, filename="file.wav"):
        WAVE_OUTPUT_FILENAME = filename
        waveFile = wave.open(WAVE_OUTPUT_FILENAME, 'wb') # 'wb' write only mode
        waveFile.setnchannels(self.channels)
        waveFile.setsampwidth(self.p.get_sample_size(self.format))
        waveFile.setframerate(self.rate)
        waveFile.writeframes(data)
        waveFile.close()
        
    def save_dataframe(self, filename='DataSet/data.pkl'):
        self.saving = True
        df = pd.DataFrame.from_records(self.df_list)
            
        # Save to pickle file
        df.to_pickle(filename)
        
        self.df_list = [] # Clear existing list data
        
        self.saving = False
        
        self.save_cnt += 1
		
		
key = KeyAudio()
key.startListener()