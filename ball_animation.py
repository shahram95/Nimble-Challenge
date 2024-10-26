import cv2
import numpy as np

class BallAnimation:
    """Class to generate frames of a bouncing ball animation."""
    
    def __init__(self, width=640, height=480, ball_radius=20, ball_speed=5):
        """
        Initialize the ball animation parameters.
        
        Args:
            width (int): Frame width in pixels
            height (int): Frame height in pixels
            ball_radius (int): Radius of the ball in pixels
            ball_speed (int): Initial speed of the ball
        """
        self.width = width
        self.height = height
        self.radius = ball_radius
        
        self.x = self.radius * 2
        self.y = self.height // 2
        self.dx = ball_speed
        self.dy = ball_speed
        
        
        self.background = np.zeros((height, width, 3), dtype=np.uint8)
        self.background.fill(32)
        
    def update_ball_position(self):
        """Update the ball position based on velocity and boundaries."""
        self.x += self.dx
        self.y += self.dy

        if self.x <= self.radius or self.x >= self.width - self.radius:
            self.dx = -self.dx
        if self.y <= self.radius or self.y >= self.height - self.radius:
            self.dy = -self.dy
            
        self.x = np.clip(self.x, self.radius, self.width - self.radius)
        self.y = np.clip(self.y, self.radius, self.height - self.radius)
    
    def get_frame(self):
        """
        Generate a new frame with the current ball position.
        
        Returns:
            numpy.ndarray: Frame with the ball drawn at current position
        """
        frame = self.background.copy()
        
        cv2.circle(
            frame,
            center=(int(self.x), int(self.y)),
            radius=self.radius,
            color=(0, 165, 255),
            thickness=-1
        )
        
        return frame
    
    def get_ball_position(self):
        """
        Get the current ball position.
        
        Returns:
            tuple: (x, y) coordinates of the ball center
        """
        return (int(self.x), int(self.y))

def test_animation():
    """Test function to visualize the animation using OpenCV window."""
    animation = BallAnimation()
    
    while True:
        frame = animation.get_frame()
        
        animation.update_ball_position()
        
        cv2.imshow('Bouncing Ball', frame)
        
        if cv2.waitKey(16) & 0xFF == ord('q'):
            break
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    test_animation()