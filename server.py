import os
import sys
import json
import time
import logging
import logging.handlers
import argparse
import asyncio
import psutil
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, List, Any
import cv2 as cv
import numpy as np
import fractions
from pathlib import Path

from aiortc import (
    MediaStreamTrack,
    RTCPeerConnection,
    RTCSessionDescription,
    RTCIceCandidate,
    RTCDataChannel
)
from aiortc.contrib.signaling import BYE, TcpSocketSignaling
from av import VideoFrame

# Setup logging
logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """Monitors system and application performance metrics"""
    def __init__(self, max_samples: int = 10):  # Reduced from 30
        self._process = psutil.Process()
        self._start_time = time.time()
        self._frame_times: List[float] = []
        self._max_samples = max_samples
        self._last_frame_time = time.time()
        self._last_gc_time = time.time()
        self._gc_interval = 5.0  # GC every 5 seconds

    def update(self) -> Dict[str, float]:
        """Update performance metrics"""
        current_time = time.time()
        frame_time = current_time - self._last_frame_time
        self._last_frame_time = current_time
        
        # Manage frame times with fixed size
        self._frame_times.append(frame_time)
        while len(self._frame_times) > self._max_samples:
            self._frame_times.pop(0)
            
        # Periodic garbage collection
        if current_time - self._last_gc_time >= self._gc_interval:
            import gc
            gc.collect()
            self._last_gc_time = current_time
            
        metrics = {
            'fps': 1 / (sum(self._frame_times) / len(self._frame_times)),
            'cpu_percent': self._process.cpu_percent(),
            'memory_mb': self._process.memory_info().rss / 1024 / 1024,
            'uptime': current_time - self._start_time
        }
        
        return metrics

@dataclass(frozen=True)
class VideoConfig:
    """Video streaming configuration parameters"""
    width: int = 640
    height: int = 480
    fps: int = 30
    clock_rate: int = 90000
    time_base: fractions.Fraction = fractions.Fraction(1, 90000)
    
    @property
    def frame_interval(self) -> float:
        """Time interval between frames in seconds"""
        return 1 / self.fps

class BallAnimation:
    """Generates frames of a bouncing ball animation"""
    def __init__(self, width=640, height=480, ball_radius=20, speed=2):
        """Initialize the animation parameters"""
        self.width = width
        self.height = height
        self.radius = ball_radius
        self.x = self.radius * 2
        self.y = self.height // 2
        self.dx = speed
        self.dy = speed
        self.background = np.zeros((height, width, 3), dtype=np.uint8)
        self.background.fill(32)

    def update_position(self):
        """Update ball position based on velocity and boundaries"""
        self.x += self.dx
        self.y += self.dy

        if self.x <= self.radius or self.x >= self.width - self.radius:
            self.dx = -self.dx
        if self.y <= self.radius or self.y >= self.height - self.radius:
            self.dy = -self.dy

        self.x = np.clip(self.x, self.radius, self.width - self.radius)
        self.y = np.clip(self.y, self.radius, self.height - self.radius)

    def get_frame(self):
        """Generate a new frame with current ball position"""
        frame = self.background.copy()
        cv.circle(
            frame,
            center=(int(self.x), int(self.y)),
            radius=self.radius,
            color=(0, 165, 255),
            thickness=-1,
            lineType=cv.LINE_AA
        )
        return frame

    def get_position(self) -> Tuple[int, int]:
        """Get current ball position"""
        return (int(self.x), int(self.y))

class VideoGenerator(MediaStreamTrack):
    """Generates video frames with an animated ball"""
    kind = "video"

    def __init__(self, config: VideoConfig):
        super().__init__()
        self._config = config
        self._animation = BallAnimation(
            width=config.width,
            height=config.height,
            ball_radius=20,
            speed=5
        )
        self._start_time: Optional[float] = None
        self._frame_count: int = 0
        self._performance = PerformanceMonitor()
        self._last_frame = None

    async def _sync_timing(self) -> Tuple[int, fractions.Fraction]:
        """Synchronize frame timing for smooth animation"""
        try:
            if self._start_time is None:
                self._start_time = time.time()
                self._frame_count = 0
            
            target_time = self._start_time + (self._frame_count * self._config.frame_interval)
            current_time = time.time()
            wait_time = max(0, target_time - current_time)
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            pts = int(self._frame_count * self._config.frame_interval * self._config.clock_rate)
            self._frame_count += 1
            
            return pts, self._config.time_base
        except Exception as e:
            logger.error(f"Timing sync error: {str(e)}")
            raise

    async def recv(self) -> VideoFrame:
        """Generate and return the next video frame"""
        try:
            # Clear previous frame if it exists
            if self._last_frame is not None:
                del self._last_frame
            
            self._animation.update_position()
            frame_array = self._animation.get_frame()
            
            # Add performance overlay
            metrics = self._performance.update()
            cv.putText(
                frame_array,
                f"FPS: {metrics['fps']:.1f} | CPU: {metrics['cpu_percent']:.1f}% | Mem: {metrics['memory_mb']:.1f}MB",
                (10, 30),
                cv.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv.LINE_AA
            )
            
            # Store current frame
            self._last_frame = frame_array
            
            frame = VideoFrame.from_ndarray(frame_array, format="bgr24")
            pts, time_base = await self._sync_timing()
            frame.pts = pts
            frame.time_base = time_base
            return frame
            
        except Exception as e:
            logger.error(f"Frame generation failed: {str(e)}")
            raise

    @property
    def ball_position(self) -> Tuple[int, int]:
        """Get current ball position"""
        return self._animation.get_position()

class PositionTracker:
    """Tracks and analyzes ball position data"""
    def __init__(self, max_history: int = 30):  # Reduced from 100
        self._position_history: List[Tuple[int, int]] = []
        self._error_history: List[float] = []
        self._max_history = max_history
        self._start_time = time.time()

    def analyze_movement(self, actual_pos: Tuple[int, int], 
                        detected_pos: Dict[str, int]) -> Dict[str, float]:
        """Compute tracking metrics"""
        try:
            error = np.sqrt(
                (actual_pos[0] - detected_pos['x']) ** 2 +
                (actual_pos[1] - detected_pos['y']) ** 2
            )
            
            # Manage history with fixed size
            self._position_history.append(actual_pos)
            self._error_history.append(error)
            
            while len(self._position_history) > self._max_history:
                self._position_history.pop(0)
                self._error_history.pop(0)
                
            return {
                'current_error': error,
                'average_error': np.mean(self._error_history),
                'max_error': np.max(self._error_history),
                'error_std': np.std(self._error_history),
                'tracking_duration': time.time() - self._start_time
            }
        except Exception as e:
            logger.error(f"Error computing metrics: {str(e)}")
            raise

class WebRTCServer:
    """WebRTC video streaming server"""
    def __init__(self, host: str, port: int):
        self._signaling = TcpSocketSignaling(host, port)
        self._connection = RTCPeerConnection()
        self._video_track = VideoGenerator(VideoConfig())
        self._tracker = PositionTracker()
        self._start_time = time.time()
        self._last_gc_time = time.time()
        self._gc_interval = 5.0  # GC every 5 seconds
        
        # Setup connection monitoring
        self._connection.on("connectionstatechange")(self._on_connection_state)


    def _on_connection_state(self):
        """Handle connection state changes"""
        logger.info(f"Connection state changed to: {self._connection.connectionState}")
        
    async def _handle_data_channel(self, channel: RTCDataChannel) -> None:
        """Handle incoming position data"""
        
        @channel.on("message")
        def on_message(message: str) -> None:
            try:
                current_time = time.time()
                
                # Periodic garbage collection
                if current_time - self._last_gc_time >= self._gc_interval:
                    import gc
                    gc.collect()
                    self._last_gc_time = current_time
                
                # Parse coordinates
                try:
                    coords = json.loads(message)
                except json.JSONDecodeError:
                    try:
                        coords = eval(message)
                    except:
                        raise ValueError(f"Invalid position data: {message}")
                
                actual_pos = self._video_track.ball_position
                metrics = self._tracker.analyze_movement(actual_pos, coords)
                
                logger.info(
                    "\nPosition Update:\n"
                    f"  Actual Position: {actual_pos}\n"
                    f"  Detected Position: ({coords['x']}, {coords['y']})\n"
                    f"  Current Error: {metrics['current_error']:.2f}px\n"
                    f"  Average Error: {metrics['average_error']:.2f}px\n"
                    f"  Error Std Dev: {metrics['error_std']:.2f}px\n"
                    f"  Tracking Duration: {metrics['tracking_duration']:.1f}s"
                )
            except Exception as e:
                logger.error(f"Data processing error: {str(e)}")

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
                elif isinstance(obj, RTCIceCandidate):
                    await self._connection.addIceCandidate(obj)
                elif obj is BYE:
                    logger.info("Received BYE signal")
                    break
            except Exception as e:
                logger.error(f"Connection error: {str(e)}")
                break

    async def start(self) -> None:
        """Start the WebRTC server"""
        try:
            logger.info(f"Starting server on {self._signaling._host}:{self._signaling._port}")
            await self._signaling.connect()
            
            channel = self._connection.createDataChannel("coordinates")
            self._connection.addTrack(self._video_track)
            await self._handle_data_channel(channel)

            await self._connection.setLocalDescription(
                await self._connection.createOffer()
            )
            await self._signaling.send(self._connection.localDescription)
            
            logger.info(f"Server ready - waiting for connections")
            await self._handle_connection()
            
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
            raise
        finally:
            uptime = time.time() - self._start_time
            logger.info(f"Shutting down after {uptime:.1f}s uptime")
            await self._connection.close()
            await self._signaling.close()

def setup_logging(verbose: bool) -> None:
    """Configure application logging"""
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Setup rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / f'server_{int(time.time())}.log',
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

def main() -> None:
    """Application entry point"""
    parser = argparse.ArgumentParser(
        description="Ball Tracking Server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", default=8080, type=int, help="Server port")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    # Add memory management options
    parser.add_argument("--gc-interval", type=float, default=5.0,
                       help="Garbage collection interval in seconds")
    parser.add_argument("--history-size", type=int, default=30,
                       help="Maximum size of tracking history")
    
    args = parser.parse_args()

    try:
        setup_logging(args.verbose)
        logger.info(f"Starting application with args: {vars(args)}")
        
        import gc
        gc.enable()  # Ensure GC is enabled
        
        server = WebRTCServer(args.host, args.port)
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        # Final cleanup
        gc.collect()
        sys.exit(0)

if __name__ == "__main__":
    main()