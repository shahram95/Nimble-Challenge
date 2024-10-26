# Nimble Programming Challenge

## Setup instructions

To set up the environment for this project, please follow these steps:

1. **Create a new Conda environment:**
   ```bash
   conda create -n "nimble_env" python=3.10 pip
   ```

2. **Activate the Conda environment:**
   ```bash
   conda activate nimble_env
   ```

3. **Install the required packages:**
   ```bash
   pip install -r requirements.txt
   ```


## Skills Needed
- Linux (Ubuntu 22.04+ recommended)
- Python 3 (3.10+ recommended)
- Python numpy (http://www.numpy.org/)
- Python opencv (https://pypi.org/project/opencv-python/)
- Python aiortc (https://github.com/aiortc/aiortc)
- Python multiprocessing (https://docs.python.org/3.10/library/multiprocessing.html)

## Requirements

- [x] **1. Server Program**
  - Make a server python program that runs from the command line (`python3 server.py`).

- [ ] **2. Client Program**
  - Make a client python program that runs from the command line (`python3 client.py`).

- [ ] **3. Using `aiortc` built-in `TcpSocketSignaling`**
  - [x] (a) The server should create an `aiortc offer` and send to client.
  - [ ] (b) The client should receive the offer and create an `aiortc answer`.

- [ ] **4. Image Generation**
  - The server should generate a continuous 2D image/frames of a ball bouncing across the screen.

- [ ] **5. Image Transmission**
  - The server should transmit these images to the client via `aiortc` using frame transport (extend `aiortc.MediaStreamTrack`).

- [ ] **6. Image Display**
  - The client should display the received images using `opencv`.

- [ ] **7. Multiprocessing Process**
  - The client should start a new `multiprocessing.Process` (process_a).

- [ ] **8. Frame Communication**
  - The client should send every received frame to this process using a `multiprocessing.Queue`.

- [ ] **9. Image Parsing**
  - The client `process_a` should parse the image and determine the current location of the ball as `x,y` coordinates.

- [ ] **10. Coordinate Storage**
  - The client `process_a` should store the computed `x,y` coordinate as a `multiprocessing.Value`.

- [ ] **11. Data Channel Communication**
  - The client should open an `aiortc` data channel to the server and send each `x,y` coordinate to the server. These coordinates are from `process_a` but sent to the server from the client main thread.

- [ ] **12. Error Computation**
  - The server program should display the received coordinates and compute the error to the actual location of the ball.

- [ ] **13. Documentation**
  - Document all code using python docstrings.

- [ ] **14. Unit Tests**
  - Write unit tests for all functions which will be executed by pytest (`pytest test_YOUR_SCRIPT.py`).

- [ ] **15. README**
  - Include a `README` file.

- [ ] **16. Screen Capture**
  - Include a screen capture (mp4, mkv, avi, etc.) of your application in action.

- [ ] **17. Project Compression**
  - Compress the project directory and include your name in the filename. Do not post solutions publicly.

- [ ] **18. Docker Image**
  - [ ] (a) Make a `docker` image (Dockerfile) for the server.
  - [ ] (b) Make a `docker` image (Dockerfile) for the client.

- [ ] **19. Kubernetes**
  - [ ] (a) Create `kubernetes` manifest yaml files for client and server deployment.
  - [ ] (b) Docs for deploying it (using `minikube/k3s/microk8s` etc.).