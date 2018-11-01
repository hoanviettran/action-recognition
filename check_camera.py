import cv2

if __name__ == '__main__':
    cap = cv2.VideoCapture('/media/hoantranviet/data/ImageProcessing/VideoTest/Test2.mp4')
    print(cap.get(cv2.CAP_PROP_FPS))
    while True:
        ret, frame = cap.read()
        if(ret):
            cv2.imshow('frame', frame)
            if(cv2.waitKey() == ord('q')):
                cv2.destroyAllWindows()
                break
            cv2.destroyAllWindows()


