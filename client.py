#!/usr/bin/env python3
import asyncio
import argparse
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.signaling import TcpSocketSignaling

async def run_client(signaling):
    """
    Run the WebRTC client with TCP signaling.
    
    Args:
        signaling: TcpSocketSignaling instance for connection handling
    """

    pc = RTCPeerConnection()
    
    @pc.on("track")
    def on_track(track):
        print(f"Receiving {track.kind} track")
        
    @pc.on("datachannel")
    def on_datachannel(channel):
        print(f"Received data channel: {channel.label}")
        
        @channel.on("open")
        def on_open():
            print("Data channel is open")
            
        @channel.on("message")
        def on_message(message):
            print(f"Received message: {message}")
    
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "failed":
            await pc.close()
    
    await signaling.connect()
    
    offer = await signaling.receive()
    await pc.setRemoteDescription(offer)
    
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    await signaling.send(pc.localDescription)
    
    while True:
        await asyncio.sleep(1)

def main():
    """Main function to setup and run the client."""
    parser = argparse.ArgumentParser(description="WebRTC client")
    parser.add_argument("--host", default="localhost", help="Host for TCP server")
    parser.add_argument("--port", type=int, default=8080, help="Port for TCP server")
    args = parser.parse_args()
    
    signaling = TcpSocketSignaling(args.host, args.port)
    
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run_client(signaling))
    except KeyboardInterrupt:
        print("Client stopped by user")
    finally:
        loop.run_until_complete(signaling.close())

if __name__ == "__main__":
    main()