#!/usr/bin/env python3
"""
ZeroMQ Router Script.
Routes messages between MT4 (PUB) and FastAPI (SUB).

Usage:
    uv run scripts/zmq_router.py
"""
import asyncio
import zmq
import zmq.asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def zmq_router():
    """
    Route ZeroMQ messages between MT4 and FastAPI.
    """
    context = zmq.asyncio.Context()
    
    # SUB socket to receive from MT4
    sub_socket = context.socket(zmq.SUB)
    sub_socket.bind("tcp://0.0.0.0:5555")
    sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
    
    # PUB socket to send to FastAPI
    pub_socket = context.socket(zmq.PUB)
    pub_socket.bind("tcp://0.0.0.0:5556")
    
    logger.info("ZeroMQ Router started")
    logger.info("Listening on tcp://0.0.0.0:5555")
    logger.info("Publishing on tcp://0.0.0.0:5556")
    
    try:
        while True:
            try:
                # Receive from MT4
                message = await sub_socket.recv_multipart()
                logger.info(f"Received from MT4: {message[0]}")
                
                # Forward to FastAPI
                await pub_socket.send_multipart(message)
                logger.debug("Forwarded to FastAPI")
                
            except Exception as e:
                logger.error(f"Router error: {e}")
                await asyncio.sleep(0.1)
                
    except KeyboardInterrupt:
        logger.info("Shutting down router")
    finally:
        sub_socket.close()
        pub_socket.close()
        context.term()


if __name__ == "__main__":
    asyncio.run(zmq_router())
