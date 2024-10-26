#!/usr/bin/env python3
import asyncio
import argparse
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.signaling import TcpSocketSignaling

class DummyVideoTrack(MediaStreamTrack):
    """
    A dummy video track that will be replaced with bouncing ball animation later.
    """
    kind = "video"

    async def recv(self):
        await asyncio.sleep(1/30)  # 30fps
        frame = None
        return frame

async def run_server(signaling):
    """
    Run the WebRTC server with TCP signaling.
    
    Args:
        signaling: TcpSocketSignaling instance for connection handling
    """
    pc = RTCPeerConnection()
    
    video_track = DummyVideoTrack()
    pc.addTrack(video_track)    
    data_channel = pc.createDataChannel("coordinates")
    
    @data_channel.on("open")
    def on_open():
        print("Data channel is open")

    @data_channel.on("message")
    def on_message(message):
        print(f"Received coordinates: {message}")
    
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "failed":
            await pc.close()
    
    await signaling.connect()
    
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    await signaling.send(pc.localDescription)
    
    answer = await signaling.receive()
    await pc.setRemoteDescription(answer)
    
    while True:
        await asyncio.sleep(1)

def main():
    """Main function to setup and run the server."""
    parser = argparse.ArgumentParser(description="WebRTC server")
    parser.add_argument("--host", default="0.0.0.0", help="Host for TCP server")
    parser.add_argument("--port", type=int, default=8080, help="Port for TCP server")
    args = parser.parse_args()
    
    signaling = TcpSocketSignaling(args.host, args.port)
    
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run_server(signaling))
    except KeyboardInterrupt:
        print("Server stopped by user")
    finally:
        loop.run_until_complete(signaling.close())

if __name__ == "__main__":
    main()