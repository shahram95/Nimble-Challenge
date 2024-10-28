import pytest
import numpy as np
import cv2 as cv
import json
import multiprocessing as mp
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from client import (
    StreamDisplay,
    VideoReceiver,
    BallPositionTracker,
    FrameProcessor,
    WebRTCClient,
    WindowConfig,
    BallTrackingConfig
)

# Fixtures
@pytest.fixture
def window_config():
    return WindowConfig(
        window_name="Test Window",
        window_width=800,
        window_height=600
    )

@pytest.fixture
def tracking_config():
    return BallTrackingConfig()

@pytest.fixture
def frame_queue():
    return mp.Queue(maxsize=2)

@pytest.fixture
def position_queue():
    return mp.Queue(maxsize=2)

@pytest.fixture
def test_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)

@pytest.fixture
def mock_track():
    track = MagicMock()
    track.kind = "video"
    return track

# StreamDisplay Tests
def test_stream_display_initialization(window_config):
    display = StreamDisplay(window_config)
    assert not display._is_window_active
    assert display._frame_count == 0

@patch('cv2.namedWindow')
@patch('cv2.resizeWindow')
def test_stream_display_window_initialization(mock_resize, mock_window, window_config):
    display = StreamDisplay(window_config)
    display.initialize_window()
    
    mock_window.assert_called_once_with(
        window_config.window_name,
        window_config.window_type
    )
    mock_resize.assert_called_once_with(
        window_config.window_name,
        window_config.window_width,
        window_config.window_height
    )
    assert display._is_window_active

@patch('cv2.imshow')
@patch('cv2.waitKey')
def test_stream_display_update(mock_wait, mock_show, window_config, test_frame):
    display = StreamDisplay(window_config)
    mock_wait.return_value = 0  # Not the quit key
    
    result = display.update_display(test_frame)
    
    assert result is True
    mock_show.assert_called_once()
    mock_wait.assert_called_once_with(window_config.frame_delay)

@patch('cv2.destroyAllWindows')
def test_stream_display_close(mock_destroy, window_config):
    display = StreamDisplay(window_config)
    display._is_window_active = True
    display.close_display()
    
    mock_destroy.assert_called_once()
    assert not display._is_window_active

# BallPositionTracker Tests
def test_ball_tracker_initialization(tracking_config):
    tracker = BallPositionTracker(tracking_config)
    assert tracker._detection_count == 0
    assert tracker._miss_count == 0

def test_ball_tracker_locate_ball_no_ball(tracking_config, test_frame):
    tracker = BallPositionTracker(tracking_config)
    result = tracker.locate_ball(test_frame)
    assert result is None
    assert tracker._miss_count == 1

@patch('cv2.HoughCircles')
def test_ball_tracker_locate_ball_found(mock_circles, tracking_config, test_frame):
    tracker = BallPositionTracker(tracking_config)
    mock_circles = np.array([[[50, 50, 20]]])  # x, y, radius
    
    with patch('cv2.HoughCircles', return_value=mock_circles):
        result = tracker.locate_ball(test_frame)
        
    assert result == (50, 50)
    assert tracker._detection_count == 1

# FrameProcessor Tests
def test_frame_processor_initialization(frame_queue, position_queue):
    processor = FrameProcessor(frame_queue, position_queue)
    assert processor._processed_frames == 0
    assert isinstance(processor._tracker, BallPositionTracker)

# VideoReceiver Tests
@pytest.mark.asyncio
async def test_video_receiver_initialization(mock_track, frame_queue):
    receiver = VideoReceiver(mock_track, frame_queue)
    assert receiver.kind == "video"
    assert receiver._frame_count == 0

@pytest.mark.asyncio
async def test_video_receiver_frame_processing(mock_track, frame_queue, test_frame):
    """Test video frame processing with correct YUV420P format"""
    # Create a properly formatted YUV420P frame
    height, width = test_frame.shape[:2]
    y_size = width * height
    u_size = v_size = y_size // 4
    yuv_frame = np.zeros(y_size + 2 * u_size, dtype=np.uint8)
    
    # Mock the frame with correct YUV420P format
    async def mock_recv():
        frame = MagicMock()
        frame.to_ndarray.return_value = yuv_frame
        return frame
    
    mock_track.recv = mock_recv
    receiver = VideoReceiver(mock_track, frame_queue)
    
    # Mock cv2.cvtColor to avoid actual conversion
    with patch('cv2.cvtColor', return_value=test_frame), \
         patch('cv2.putText', return_value=None), \
         patch('cv2.imshow', return_value=None), \
         patch('cv2.waitKey', return_value=0):
        frame = await receiver.recv()
        
    assert frame is not None
    assert receiver._frame_count == 1

# WebRTCClient Tests
def test_webrtc_client_initialization():
    client = WebRTCClient("localhost", 8080)
    assert client._data_channel is None
    assert isinstance(client._processor, FrameProcessor)

@pytest.mark.asyncio
async def test_webrtc_client_cleanup():
    """Test client cleanup with proper process handling"""
    client = WebRTCClient("localhost", 8080)
    
    # Start the processor before cleanup
    client._processor.start()
    
    # Mock the necessary components
    with patch('cv2.destroyAllWindows') as mock_destroy:
        await client._cleanup()
        
        # Verify cleanup actions
        mock_destroy.assert_called_once()
        assert not client._processor.is_alive()
        
    # Ensure proper process cleanup
    client._processor.join(timeout=1.0)

# Additional helper function for process cleanup
def cleanup_process(process):
    """Helper function to safely cleanup a process"""
    if process.is_alive():
        process.terminate()
        process.join(timeout=1.0)
        if process.is_alive():
            process.kill()
            process.join()

@patch('client.TcpSocketSignaling')
def test_webrtc_client_connection_state_change(mock_signaling):
    client = WebRTCClient("localhost", 8080)
    client._on_connection_state()
    # Verify that the connection state change was handled without errors

if __name__ == "__main__":
    pytest.main(["-v"])