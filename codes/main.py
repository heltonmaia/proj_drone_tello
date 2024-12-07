from tello_zune import TelloZune
import cv2
import tello_control
from tello_control import stop_receiving

#cap = cv2.VideoCapture(0)
tello = TelloZune()
tello.start_tello()

while True:
    #ret, frame = cap.read()
    frame = tello.get_frame()
    tello.calc_fps(frame)
    frame = cv2.resize(frame, (960, 720))
    frame = tello_control.moves(tello, frame)
    cv2.imshow('QR Code', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        stop_receiving.set() # Para encerrar a thread de busca
        break
#cap.release()
tello.end_tello()
cv2.destroyAllWindows()

