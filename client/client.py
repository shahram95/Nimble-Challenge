import os
import sys
import json
import time
import queue
import warnings
import logging
import logging.handlers
import argparse
import asyncio
import multiprocessing as mp
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, Any
from pathlib import Path
import psutil
import cv2 as cv
import numpy as np

from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    RTCIceCandidate,
    MediaStreamTrack,
)
from aiortc.contrib.signaling import TcpSocketSignaling, BYE
from aiortc.contrib.media import MediaRelay

# Configure environment
os.environ.update({
    'AV_LOG_LEVEL': 'quiet',
    'LIBAV_LOG_LEVEL': 'quiet',
    'OPENCV_LOG_LEVEL': 'OFF',
    'PYAV_LOG_LEVEL': 'quiet'
})

# Suppress warnings
warnings.filterwarnings('ignore')
logging.getLogger('libav').setLevel(logging.CRITICAL)
logging.getLogger('av').setLevel(logging.CRITICAL)

logger = logging.getLogger("client")

class PerformanceMonitor:
    """Monitors system and application performance"""
    def __init__(self, max_samples: int = 10): 
        self._process = psutil.Process()
        self._start_time = time.time()
        self._frame_times = []
        self._last_frame_time = time.time()
        self._max_samples = max_samples
        
    def update(self) -> Dict[str, float]:
        """Update and return performance metrics"""
        current_time = time.time()
        frame_time = current_time - self._last_frame_time
        self._last_frame_time = current_time
        
        self._frame_times.append(frame_time)
        while len(self._frame_times) > self._max_samples:
            self._frame_times.pop(0)
            
        metrics = {
            'fps': 1 / (sum(self._frame_times) / len(self._frame_times)),
            'cpu_percent': self._process.cpu_percent(),
            'memory_mb': self._process.memory_info().rss / 1024 / 1024,
            'uptime': current_time - self._start_time
        }
        
        return metrics

@dataclass
class WindowConfig:
    """Configuration for video window settings"""
    window_name: str = "Remote Stream"
    window_type: int = cv.WINDOW_NORMAL
    frame_delay: int = 1
    quit_key: str = 'q'
    window_width: int = 800
    window_height: int = 600

@dataclass
class BallTrackingConfig:
    """Configuration for ball tracking parameters"""
    blur_kernel: Tuple[int, int] = (5, 5)
    dp: float = 1.2
    min_dist: int = 50
    param1: int = 80
    param2: int = 25
    min_radius: int = 18
    max_radius: int = 22
    ball_color_lower: Tuple[int, int, int] = (0, 140, 220)
    ball_color_upper: Tuple[int, int, int] = (50, 190, 255)
    detection_interval: float = 0.033  # ~30 FPS

class StreamDisplay:
    """Handles video stream display operations"""
    
    def __init__(self, config: WindowConfig = WindowConfig()):
        self._config = config
        self._is_window_active = False
        self._performance = PerformanceMonitor()
        self._frame_count = 0
        
    def initialize_window(self):
        """Initialize display window if not already created"""
        if not self._is_window_active:
            cv.namedWindow(self._config.window_name, self._config.window_type)
            cv.resizeWindow(self._config.window_name, 
                          self._config.window_width, 
                          self._config.window_height)
            self._is_window_active = True
            
    def update_display(self, frame: np.ndarray) -> bool:
        """Update display with new frame and handle user input"""
        try:
            if frame is None or frame.size == 0:
                return True
                
            self.initialize_window()
            
            # Add performance overlay
            metrics = self._performance.update()
            cv.putText(
                frame,
                f"FPS: {metrics['fps']:.1f} | CPU: {metrics['cpu_percent']:.1f}% | Mem: {metrics['memory_mb']:.0f}MB",
                (10, 400),
                cv.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            
            self._frame_count += 1
            cv.putText(
                frame,
                f"Frames: {self._frame_count}",
                (10, 60),
                cv.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            
            cv.imshow(self._config.window_name, frame)
            key = cv.waitKey(self._config.frame_delay) & 0xFF
            return key != ord(self._config.quit_key)
            
        except Exception as e:
            logger.error(f"Display error: {str(e)}")
            return True

    def close_display(self):
        """Close display window and cleanup resources"""
        if self._is_window_active:
            cv.destroyAllWindows()
            self._is_window_active = False
            logger.info(f"Display closed after {self._frame_count} frames")

class VideoReceiver(MediaStreamTrack):
    """Handles video stream reception and display"""
    kind = "video"

    def __init__(self, track: MediaStreamTrack, frame_queue: mp.Queue):
        super().__init__()
        self._track = track
        self._frame_queue = frame_queue
        self._display = StreamDisplay()
        self._start_time = time.time()
        self._frame_count = 0
        self._last_log_time = time.time()
        self._last_frame = None

    async def recv(self) -> Any:
        """Receive and process incoming video frame"""
        try:
            frame = await self._track.recv()
            self._frame_count += 1
            
            # Convert frame
            video_frame = frame.to_ndarray(format="yuv420p")
            if self._last_frame is not None:
                del self._last_frame
            
            bgr_frame = cv.cvtColor(video_frame, cv.COLOR_YUV2BGR_I420)
            self._last_frame = bgr_frame
            
            if bgr_frame is not None and bgr_frame.size > 0:
                if self._display.update_display(bgr_frame):
                    try:
                        # Make a copy before putting in queue
                        self._frame_queue.put_nowait(bgr_frame.copy())
                    except queue.Full:
                        logger.warning("Frame queue full, skipping frame")
                else:
                    self._display.close_display()
                    
            # Log stats every 5 seconds
            current_time = time.time()
            if current_time - self._last_log_time >= 5:
                elapsed = current_time - self._start_time
                logger.info(
                    f"Received {self._frame_count} frames in {elapsed:.1f}s "
                    f"({self._frame_count/elapsed:.1f} FPS)"
                )
                self._last_log_time = current_time
                    
            return frame
            
        except Exception as e:
            logger.error(f"Frame reception error: {str(e)}")
            raise

class BallPositionTracker:
    """Tracks ball position in video frames"""
    
    def __init__(self, config: BallTrackingConfig = BallTrackingConfig()):
        self._config = config
        self._last_detection_time = 0
        self._detection_count = 0
        self._miss_count = 0
        
    def locate_ball(self, frame: np.ndarray) -> Optional[Tuple[int, int]]:
        """Locate ball in frame and return center coordinates"""
        current_time = time.time()
        
        # Rate limit detection
        if current_time - self._last_detection_time < self._config.detection_interval:
            return None
            
        try:
            gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
            blurred = cv.blur(gray, self._config.blur_kernel)
            
            circles = cv.HoughCircles(
                blurred,
                cv.HOUGH_GRADIENT,
                self._config.dp,
                self._config.min_dist,
                param1=self._config.param1,
                param2=self._config.param2,
                minRadius=self._config.min_radius,
                maxRadius=self._config.max_radius
            )
            
            self._last_detection_time = current_time
            
            if circles is not None:
                circles = np.uint16(np.around(circles))
                if len(circles[0, :]) > 0:
                    x, y, _ = circles[0, :][0]
                    self._detection_count += 1
                    if self._detection_count % 100 == 0:
                        detection_rate = self._detection_count / (self._detection_count + self._miss_count)
                        logger.info(f"Ball detection rate: {detection_rate:.1%}")
                    return (int(x), int(y))
                    
            self._miss_count += 1
            return None
                    
        except Exception as e:
            logger.error(f"Ball tracking error: {str(e)}")
            return None

class FrameProcessor(mp.Process):
    """Processes video frames to track ball position"""

    def __init__(self, frame_queue: mp.Queue, position_queue: mp.Queue):
        super().__init__()
        self._frame_queue = frame_queue
        self._position_queue = position_queue
        self._tracker = BallPositionTracker()
        self._current_pos = mp.Array('i', [0, 0])
        self._processed_frames = 0
        self._start_time = time.time()
        self._last_frame = None
        self._last_log_time = time.time()

    def run(self):
        """Main frame processing loop"""
        logger.info("Frame processor started")
        
        while True:
            try:
                # Use get with timeout to avoid busy waiting
                frame = self._frame_queue.get(timeout=0.1)
                
                # Clear previous frame
                if self._last_frame is not None:
                    del self._last_frame
                self._last_frame = frame
                
                if frame is not None and frame.size > 0:
                    self._processed_frames += 1
                    
                    ball_pos = self._tracker.locate_ball(frame)
                    if ball_pos:
                        self._current_pos[0], self._current_pos[1] = ball_pos
                        try:
                            position = json.dumps({
                                "x": self._current_pos[0],
                                "y": self._current_pos[1]
                            })
                            self._position_queue.put_nowait(position)
                        except queue.Full:
                            logger.warning("Position queue full, skipping update")
                    
                    # Log every 5 seconds
                    current_time = time.time()
                    if current_time - self._last_log_time >= 5:
                        elapsed = current_time - self._start_time
                        logger.info(
                            f"Processed {self._processed_frames} frames in {elapsed:.1f}s "
                            f"({self._processed_frames/elapsed:.1f} FPS)"
                        )
                        self._last_log_time = current_time
                
                # Explicitly delete the frame after processing
                del frame
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Frame processing error: {str(e)}")
                continue

class WebRTCClient:
    """WebRTC client for ball tracking application"""

    def __init__(self, host: str, port: int):
        self._signaling = TcpSocketSignaling(host, port)
        self._connection = RTCPeerConnection()
        # Reduced queue sizes
        self._frame_queue = mp.Queue(maxsize=2)
        self._position_queue = mp.Queue(maxsize=2)
        self._data_channel: Optional[Any] = None
        self._processor = FrameProcessor(self._frame_queue, self._position_queue)
        self._processor.daemon = True
        self._start_time = time.time()
        self._last_gc_time = time.time()
        self._gc_interval = 5.0  # GC every 5 seconds

    def _on_connection_state(self):
        """Handle connection state changes"""
        logger.info(f"Connection state changed to: {self._connection.connectionState}")

    async def _handle_connection(self) -> None:
        """Handle WebRTC connection and signaling"""
        while True:
            try:
                obj = await self._signaling.receive()
                
                if isinstance(obj, RTCSessionDescription):
                    await self._connection.setRemoteDescription(obj)
                    if obj.type == "offer":
                        await self._connection.setLocalDescription(
                            await self._connection.createAnswer()
                        )
                        await self._signaling.send(self._connection.localDescription)
                        logger.info("Sent answer to server")
                elif isinstance(obj, RTCIceCandidate):
                    await self._connection.addIceCandidate(obj)
                elif obj is BYE:
                    logger.info("Received BYE signal")
                    break
            except Exception as e:
                logger.error(f"Connection error: {str(e)}")
                break

    async def _send_position(self):
        """Send ball position updates to server"""
        updates_sent = 0
        last_log_time = time.time()
        
        while True:
            try:
                current_time = time.time()
                
                # Periodic garbage collection
                if current_time - self._last_gc_time >= self._gc_interval:
                    import gc
                    gc.collect()
                    self._last_gc_time = current_time
                
                if (
                    self._data_channel
                    and self._data_channel.readyState == "open"
                    and not self._position_queue.empty()
                ):
                    position = self._position_queue.get_nowait()
                    self._data_channel.send(position)
                    updates_sent += 1
                    
                    # Log every 5 seconds
                    if current_time - last_log_time >= 5:
                        elapsed = current_time - self._start_time
                        logger.info(
                            f"Sent {updates_sent} position updates in {elapsed:.1f}s "
                            f"({updates_sent/elapsed:.1f} updates/s)"
                        )
                        last_log_time = current_time
                        
                await asyncio.sleep(0.01)
            except queue.Empty:
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Position sending error: {str(e)}")
                await asyncio.sleep(0.01)

    async def start(self) -> None:
        """Start the WebRTC client"""
        try:
            logger.info(f"Connecting to server at {self._signaling._host}:{self._signaling._port}")
            await self._signaling.connect()

            @self._connection.on("track")
            def on_track(track):
                if track.kind == "video":
                    relay = MediaRelay()
                    video_track = VideoReceiver(relay.subscribe(track), self._frame_queue)
                    self._connection.addTrack(video_track)
                    logger.info("Video track received and processing started")

            @self._connection.on("datachannel")
            def on_datachannel(channel):
                self._data_channel = channel
                logger.info(f"Data channel '{channel.label}' established")

            self._processor.start()
            logger.info("Frame processor started")
            
            await asyncio.gather(
                self._handle_connection(),
                self._send_position()
            )

        except Exception as e:
            logger.error(f"Client error: {str(e)}")
        finally:
            await self._cleanup()

    async def _cleanup(self):
        """Clean up resources"""
        logger.info(f"Cleaning up after {time.time() - self._start_time:.1f}s runtime...")
        cv.destroyAllWindows()
        self._processor.terminate()
        self._processor.join(timeout=5.0)  # Wait up to 5 seconds for processor to stop
        await self._connection.close()
        await self._signaling.close()
        logger.info("Cleanup completed")

def setup_logging(verbose: bool) -> None:
    """Configure application logging
    
    Args:
        verbose: Enable verbose (debug) logging
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Setup rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / f'client_{int(time.time())}.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    
    # Setup handlers
    handlers = [
        logging.StreamHandler(),
        file_handler
    ]
    
    # Basic config
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers
    )
    
    # Suppress noisy loggers
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('aioice').setLevel(logging.WARNING)

def main():
    """Application entry point"""
    parser = argparse.ArgumentParser(
        description="WebRTC Ball Tracking Client",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--host", default="127.0.0.1", help="Signaling server host")
    parser.add_argument("--port", type=int, default=8080, help="Signaling server port")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--window-width", type=int, default=800, help="Display window width")
    parser.add_argument("--window-height", type=int, default=600, help="Display window height")
    args = parser.parse_args()

    try:
        # Setup logging first
        setup_logging(args.verbose)
        logger.info(f"Starting application with args: {vars(args)}")
        
        # Create and configure client
        client = WebRTCClient(args.host, args.port)
        loop = asyncio.get_event_loop()
        
        # Start client
        loop.run_until_complete(client.start())
        
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        cv.destroyAllWindows()
        loop.close()
        logger.info("Application terminated")

if __name__ == "__main__":
    main()