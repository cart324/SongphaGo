import wave


# Function to read and display .wav file header information
def read_wav_header(filename):
    with wave.open(filename, 'rb') as wav_file:
        # Read the parameters from the header
        nchannels, sampwidth, framerate, nframes, comptype, compname = wav_file.getparams()

        # Display the header information
        print(f"Number of channels: {nchannels}")
        print(f"Sample width: {sampwidth}")
        print(f"Frame rate: {framerate}")
        print(f"Number of frames: {nframes}")
        print(f"Compression type: {comptype}")
        print(f"Compression name: {compname}")


# Function to recover the header of a .wav file
def recover_wav_header(input_filename, output_filename):
    # Read the damaged .wav file
    with open(input_filename, 'rb') as input_file:
        data = input_file.read()

    # Find the beginning of the RIFF header
    riff_idx = data.find(b'RIFF')

    # If the RIFF header is found, proceed to recover the file
    if riff_idx != -1:
        # Extract the RIFF header and data
        riff_header = data[riff_idx:riff_idx + 44]  # RIFF header is 44 bytes
        audio_data = data[riff_idx + 44:]

        # Write the recovered .wav file
        with wave.open(output_filename, 'wb') as output_file:
            # Set the parameters for the output file
            output_file.setnchannels(2)  # Assuming stereo
            output_file.setsampwidth(2)  # Assuming 16-bit samples
            output_file.setframerate(44100)  # Assuming 44100Hz sample rate
            output_file.writeframes(audio_data)
    else:
        print("RIFF header not found. The file may not be a .wav file or is too corrupted.")


# Example usage
read_wav_header('recordings/344384179552780289.wav')  # Replace with your .wav file name
recover_wav_header('recordings/344384179552780289.wav', 'recordings/recovered.wav')  # Replace with your actual file names
