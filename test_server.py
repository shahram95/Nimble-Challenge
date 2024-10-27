import pytest
import numpy as np
from av import VideoFrame
import fractions
import asyncio
from dataclasses import dataclass
import time

from aiortc import RTCPeerConnection, RTCDataChannel
from server import (
    VideoGenerator,
    BallAnimation,
    PositionTracker,
    WebRTCServer,
    VideoConfig
)

# Test fixtures
@pytest.fixture
def video_config():
    return VideoConfig(
        width=640,
        height=480,
        fps=30,
        clock_rate=90000,
        time_base=fractions.Fraction(1, 90000)
    )

@pytest.fixture
def ball_animation():
    return BallAnimation(width=640, height=480, ball_radius=20, speed=2)

@pytest.fixture
def video_generator(video_config):
    return VideoGenerator(video_config)

@pytest.fixture
def position_tracker():
    return PositionTracker(max_history=30)

# BallAnimation tests
def test_ball_animation_initialization():
    animation = BallAnimation(width=640, height=480, ball_radius=20, speed=2)
    assert animation.width == 640
    assert animation.height == 480
    assert animation.radius == 20
    assert isinstance(animation.background, np.ndarray)
    assert animation.background.shape == (480, 640, 3)

def test_ball_animation_movement():
    animation = BallAnimation(width=640, height=480, ball_radius=20, speed=2)
    initial_x, initial_y = animation.x, animation.y
    animation.update_position()
    assert (animation.x != initial_x) or (animation.y != initial_y)
    assert animation.x >= animation.radius
    assert animation.x <= animation.width - animation.radius
    assert animation.y >= animation.radius
    assert animation.y <= animation.height - animation.radius

def test_ball_animation_frame_generation():
    animation = BallAnimation()
    frame = animation.get_frame()
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (480, 640, 3)
    assert frame.dtype == np.uint8

# VideoGenerator tests
@pytest.mark.asyncio
async def test_video_generator_initialization(video_generator):
    assert video_generator.kind == "video"
    assert isinstance(video_generator._animation, BallAnimation)
    assert video_generator._start_time is None
    assert video_generator._frame_count == 0

@pytest.mark.asyncio
async def test_video_generator_frame_generation(video_generator):
    frame = await video_generator.recv()
    assert isinstance(frame, VideoFrame)
    assert frame.width == 640
    assert frame.height == 480
    assert frame.pts is not None
    assert frame.time_base == fractions.Fraction(1, 90000)

@pytest.mark.asyncio
async def test_video_generator_multiple_frames(video_generator):
    frame1 = await video_generator.recv()
    frame2 = await video_generator.recv()
    assert frame1.pts < frame2.pts
    assert frame1 is not frame2

def test_video_generator_ball_position(video_generator):
    pos = video_generator.ball_position
    assert isinstance(pos, tuple)
    assert len(pos) == 2
    assert all(isinstance(coord, int) for coord in pos)

# PositionTracker tests
def test_position_tracker_initialization():
    tracker = PositionTracker(max_history=30)
    assert len(tracker._position_history) == 0
    assert len(tracker._error_history) == 0
    assert tracker._max_history == 30

def test_position_tracker_analysis():
    tracker = PositionTracker()
    actual_pos = (100, 100)
    detected_pos = {"x": 105, "y": 95}
    
    metrics = tracker.analyze_movement(actual_pos, detected_pos)
    
    assert isinstance(metrics, dict)
    assert "current_error" in metrics
    assert "average_error" in metrics
    assert "max_error" in metrics
    assert "error_std" in metrics
    assert "tracking_duration" in metrics
    
    # Check error calculation
    expected_error = np.sqrt((100 - 105)**2 + (100 - 95)**2)
    assert np.isclose(metrics["current_error"], expected_error)

def test_position_tracker_history_limit():
    tracker = PositionTracker(max_history=3)
    for i in range(5):
        tracker.analyze_movement((i, i), {"x": i+1, "y": i+1})
    assert len(tracker._position_history) == 3
    assert len(tracker._error_history) == 3

# WebRTCServer integration tests
@pytest.mark.asyncio
async def test_webrtc_server_initialization():
    server = WebRTCServer("127.0.0.1", 8080)
    assert isinstance(server._connection, RTCPeerConnection)
    assert isinstance(server._video_track, VideoGenerator)
    assert isinstance(server._tracker, PositionTracker)
    
    # Clean up
    await server._connection.close()

@pytest.mark.asyncio
async def test_webrtc_server_data_channel():
    server = WebRTCServer("127.0.0.1", 8080)
    channel = server._connection.createDataChannel("test")
    
    assert isinstance(channel, RTCDataChannel)
    assert channel.label == "test"
    
    # Clean up
    await server._connection.close()

if __name__ == "__main__":
    pytest.main(["-v"])