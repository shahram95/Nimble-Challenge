# Ball Tracking with WebRTC

A real-time ball tracking application using WebRTC for video streaming and coordinate transmission. The server generates an animated bouncing ball, streams it to the client, and receives back the detected ball coordinates for accuracy analysis.

## Features

- Real-time video streaming using WebRTC
- Animated bouncing ball generation
- Multi-process ball position detection
- Bi-directional communication (video stream and coordinate data)
- Performance monitoring and metrics
- Comprehensive error analysis
- Automated testing suite

## Prerequisites

### This challenge was primarily coded up in macOS, and tested on Windows 11 and Ubuntu 20.04.

- Python 3.10 or higher
- Conda (recommended for environment management)
- Linux, macOS, or Windows operating system

## Installation

1. Create a new Conda environment:
    ```bash
    conda create -n "nimble_env" python=3.10 pip
    ```

2. Activate the environment:
    ```bash
    conda activate nimble_env
    ```

3. Goto directory:
    ```bash
    cd <path to directory>/Nimble-Challenge
    ```

4. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### `requirements.txt`
```plaintext
aiortc==1.9.0
opencv-python==4.10.0.84
numpy==2.1.2
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-mock==3.14.0
av==12.3.0
aioice==0.9.0
pyee==12.0.0
pylibsrtp==0.10.0
cryptography==43.0.3
google-crc32c==1.6.0
cffi==1.17.1
psutil==6.1.0
```
## Known Issues and Workarounds

### OpenCV and PyAV Compatibility

There is a known compatibility issue between PyAV (used by `aiortc`) and OpenCV's `imshow` function. The issue causes the application to hang when importing `aiortc` before using `cv2.imshow`.

**Workaround:**

Initialize the OpenCV window before importing `aiortc`:
```python
import cv2
import numpy as np

# Initialize window first
cv2.namedWindow("video", cv2.WINDOW_NORMAL)
img = np.zeros((480, 640, 3), dtype=np.uint8)
cv2.imshow('video', img)
cv2.waitKey(1)

# Then import aiortc
import aiortc
```
For more information, see:

- [aiortc Issue #734](https://github.com/aiortc/aiortc/issues/734)
- [PyAV Issue #978](https://github.com/mikeboers/PyAV/issues/978)

## Usage

1. Start the server:
    ```bash
    python server.py [--host HOST] [--port PORT] [--verbose]
    ```

2. In a separate terminal, start the client:
    ```bash
    python client.py [--host HOST] [--port PORT] [--verbose] [--window-width WIDTH] [--window-height HEIGHT]
    ```

### Command Line Arguments

#### Server
- `--host`: Server host address (default: 127.0.0.1)
- `--port`: Server port number (default: 8080)
- `--verbose`: Enable verbose logging
- `--gc-interval`: Garbage collection interval in seconds (default: 5.0)
- `--history-size`: Maximum size of tracking history (default: 30)

#### Client
- `--host`: Server host address (default: 127.0.0.1)
- `--port`: Server port number (default: 8080)
- `--verbose`: Enable verbose logging
- `--window-width`: Display window width (default: 800)
- `--window-height`: Display window height (default: 600)

## Project Structure
```plaintext
ball-tracking/
├── server.py           # Server implementation
├── client.py           # Client implementation
├── test_server.py      # Server unit tests
├── test_client.py      # Client unit tests
├── requirements.txt    # Project dependencies
├── README.md           # This file
└── logs/               # Application logs directory
```

## Testing

Run the test suite using `pytest`:
```bash
pytest test_server.py test_client.py -v
```

## Logging

Both server and client applications generate detailed logs in the `logs` directory. Logs include:
- Performance metrics
- Connection states
- Ball tracking accuracy
- Error conditions

Log files use a rotating file handler with a maximum size of 10MB and keep up to 5 backup files.

## Performance Considerations

- The application uses multiprocessing for ball detection to prevent UI blocking.
- Garbage collection is performed at regular intervals.
- Frame and position queues are size-limited to prevent memory issues.
- Performance metrics are displayed in real-time.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
