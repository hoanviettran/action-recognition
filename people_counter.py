# USAGE
# To read and write back out to video:
# python people_counter.py --prototxt mobilenet_ssd/MobileNetSSD_deploy.prototxt \
#	--model mobilenet_ssd/MobileNetSSD_deploy.caffemodel --input videos/example_01.mp4 \
#	--output output/output_01.avi
#
# To read from webcam and write back out to disk:
# python people_counter.py --prototxt mobilenet_ssd/MobileNetSSD_deploy.prototxt \
#	--model mobilenet_ssd/MobileNetSSD_deploy.caffemodel \
#	--output output/webcam_output.avi

# import the necessary packages
from pyimagesearch.centroidtracker import CentroidTracker
from pyimagesearch.trackableobject import TrackableObject
from imutils.video import VideoStream
from imutils.video import FPS
import numpy as np
import argparse
import imutils
import time
import dlib
import cv2
import motempl
from motempl import nothing 


# Get the names of the output layers
def getOutputsNames(net):
    # Get the names of all the layers in the network
    layersNames = net.getLayerNames()
    # Get the names of the output layers, i.e. the layers with unconnected outputs
    return [layersNames[i[0] - 1] for i in net.getUnconnectedOutLayers()]

# construct the argument parse and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-p", "--prototxt", #required=True,
	# default='/media/hoantranviet/data/ImageProcessing/people-counting-opencv/mobilenet_ssd/MobileNetSSD_deploy.prototxt',
	# default='/media/hoantranviet/data/ImageProcessing/pertrained-models/faster_rcnn_inception_v2_coco_2018_01_28/faster_rcnn_inception_v2_coco_2018_01_28.pbtxt',
	default='/home/hoantranviet/pytorch-yolo-v3/cfg/yolov3.cfg',
	help="path to Caffe 'deploy' prototxt file")
ap.add_argument("-m", "--model", #required=True,
	default='/home/hoantranviet/pytorch-yolo-v3/yolov3.weights',
	# default='/media/hoantranviet/data/ImageProcessing/people-counting-opencv/mobilenet_ssd/MobileNetSSD_deploy.caffemodel',
	# default='/media/hoantranviet/data/ImageProcessing/pertrained-models/faster_rcnn_inception_v2_coco_2018_01_28/frozen_inference_graph.pb',
	help="path to Caffe pre-trained model")
ap.add_argument("-i", "--input", type=str,
	default='/home/hoantranviet/Downloads/rawvideo/1.mp4',
	help="path to optional input video file")
ap.add_argument("-o", "--output", type=str,
	help="path to optional output video file")
ap.add_argument("-c", "--confidence", type=float, default=0.7,
	help="minimum probability to filter weak detections")
ap.add_argument("-s", "--skip-frames", type=int, default=10,
	help="# of skip frames between detections")
args = vars(ap.parse_args())

# initialize the list of class labels MobileNet SSD was trained to
# detect
CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat",
	"bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
	"dog", "horse", "motorbike", "person", "pottedplant", "sheep",
	"sofa", "train", "tvmonitor"]

# load our serialized model from disk
print("[INFO] loading model...")
# net = cv2.dnn.readNetFromCaffe(args["prototxt"], args["model"])
# net = cv2.dnn.readNetFromTensorflow(args["model"],args["prototxt"])
net = cv2.dnn.readNetFromDarknet(args["prototxt"], args["model"])

#backends = (cv.dnn.DNN_BACKEND_DEFAULT, cv.dnn.DNN_BACKEND_HALIDE, cv.dnn.DNN_BACKEND_INFERENCE_ENGINE, cv.dnn.DNN_BACKEND_OPENCV)
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_DEFAULT)
#targets = (cv.dnn.DNN_TARGET_CPU, cv.dnn.DNN_TARGET_OPENCL, cv.dnn.DNN_TARGET_OPENCL_FP16, cv.dnn.DNN_TARGET_MYRIAD)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

# if a video path was not supplied, grab a reference to the webcam
if not args.get("input", False):
	print("[INFO] starting video stream...")
	vs = VideoStream(src=0).start()
	time.sleep(2.0)

# otherwise, grab a reference to the video file
else:
	print("[INFO] opening video file...")
	vs = cv2.VideoCapture(args["input"])

# initialize the video writer (we'll instantiate later if need be)
writer = None

# initialize the frame dimensions (we'll set them as soon as we read
# the first frame from the video)
W = None
H = None

# instantiate our centroid tracker, then initialize a list to store
# each of our dlib correlation trackers, followed by a dictionary to
# map each unique object ID to a TrackableObject
ct = CentroidTracker(maxDisappeared=40, maxDistance=200)
trackers = []
trackableObjects = {}

# initialize the total number of frames processed thus far, along
# with the total number of objects that have moved either up or down
totalFrames = 0
totalDown = 0
totalUp = 0

# start the frames per second throughput estimator
fps = FPS().start()
DEFAULT_THRESHOLD = 32
MHI_DURATION = 0.5
MHI_NUM_FRAMES = 16
# cv2.namedWindow('motempl')
# visuals = ['input', 'frame_diff', 'motion_hist', 'grad_orient']
# cv2.createTrackbar('visual', 'motempl', 2, len(visuals)-1, nothing)
# cv2.createTrackbar('threshold', 'motempl', DEFAULT_THRESHOLD, 255, nothing)
ret , frame = vs.read()
# prev_frame = imutils.resize(frame, width=500)
prev_frame = frame.copy()
prev_frame = imutils.resize(prev_frame, width=1280, height=720)
h, w = prev_frame.shape[:2]
motion_history = np.zeros((h, w), np.float32)

# loop over frames from the video stream
while True:
	# grab the next frame and handle if we are reading from either
	# VideoCapture or VideoStream
	frame = vs.read()
	frame = frame[1] if args.get("input", False) else frame

	# if we are viewing a video and we did not grab a frame then we
	# have reached the end of the video
	if args["input"] is not None and frame is None:
		break

	# resize the frame to have a maximum width of 500 pixels (the
	# less data we have, the faster we can process it), then convert
	# the frame from BGR to RGB for dlib
	frame = imutils.resize(frame, width=1280, height=720)
	frame_copy = frame.copy()
	rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

	# if the frame dimensions are empty, set them
	if W is None or H is None:
		(H, W) = frame.shape[:2]

	# if we are supposed to be writing a video to disk, initialize
	# the writer
	if args["output"] is not None and writer is None:
		fourcc = cv2.VideoWriter_fourcc(*"MJPG")
		writer = cv2.VideoWriter(args["output"], fourcc, 30,
			(W, H), True)

	# initialize the current status along with our list of bounding
	# box rectangles returned by either (1) our object detector or
	# (2) the correlation trackers
	status = "Waiting"
	rects = []
	frame_diff = cv2.absdiff(frame, prev_frame)
	gray_diff = cv2.cvtColor(frame_diff, cv2.COLOR_BGR2GRAY)
	# thrs = cv2.getTrackbarPos('threshold', 'motempl')
	ret, motion_mask = cv2.threshold(gray_diff, DEFAULT_THRESHOLD, 1, cv2.THRESH_BINARY)
	timestamp = cv2.getTickCount() / cv2.getTickFrequency()
	cv2.motempl.updateMotionHistory(motion_mask, motion_history, timestamp, MHI_DURATION)
	mhi_frame = np.uint8(np.clip((motion_history-(timestamp-MHI_DURATION)) / MHI_DURATION, 0, 1)*255)
	mhi_frame = cv2.cvtColor(mhi_frame, cv2.COLOR_GRAY2BGR)
	prev_frame = frame
	# check to see if we should run a more computationally expensive
	# object detection method to aid our tracker
	if totalFrames % args["skip_frames"] == 0:
		# set the status and initialize our new set of object trackers
		status = "Detecting"
		trackers = []

		# convert the frame to a blob and pass the blob through the
		# network and obtain the detections
		blob = cv2.dnn.blobFromImage(frame, 1 / 255, (416, 416), [0, 0, 0], 1, crop=False)
		# blob = cv2.dnn.blobFromImage(frame, 0.007843, (W, H), 127.5)
		net.setInput(blob)
		# detections = net.forward()
		# outs = net.forward()
		outs = net.forward(getOutputsNames(net))

		classIds = []
		confidences = []
		boxes = []

		for out in outs:
			for detection in out:
				scores = detection[5:]
				classId = np.argmax(scores)
				if(classId != 0):
					continue
				confidence = scores[classId]
				if confidence > args["confidence"]:
					center_x = int(detection[0] * W)
					center_y = int(detection[1] * H)
					width = int(detection[2] * W)
					height = int(detection[3] * H)
					left = int(center_x - width / 2)
					top = int(center_y - height / 2)
					classIds.append(classId)
					confidences.append(float(confidence))
					boxes.append([left, top, width, height])

		indices = cv2.dnn.NMSBoxes(boxes, confidences, args["confidence"], 0.4)
		for i in indices:
			i = i[0]
			box = boxes[i]
			left = box[0]
			top = box[1]
			width = box[2]
			height = box[3]
			# drawPred(classIds[i], confidences[i], left, top, left + width, top + height)

			box = np.array([left, top, left + width, top + height])

		# for detection in detections[0, 0, :, :]:
		# 	score = float(detection[2])
		# 	if score > args["confidence"]:
		# 		idx = int(detection[1])
		# 		if CLASSES[idx] != "person":
		# 			continue

		# # loop over the detections
		# for i in np.arange(0, detections.shape[2]):
		# 	# extract the confidence (i.e., probability) associated
		# 	# with the prediction
		# 	confidence = detections[0, 0, i, 2]
		#
		# 	# filter out weak detections by requiring a minimum
		# 	# confidence
		# 	if confidence > args["confidence"]:
		# 		# extract the index of the class label from the
		# 		# detections list
		# 		idx = int(detections[0, 0, i, 1])
		#
		# 		# if the class label is not a person, ignore it
		# 		# if CLASSES[idx] != "person":
		# 		if(idx != 0):
		# 			continue

			# compute the (x, y)-coordinates of the bounding box
			# for the object
			# box = detection[3:7] * np.array([W, H, W, H])
			(startX, startY, endX, endY) = box.astype("int")
			cv2.rectangle(frame_copy,(startX, startY), (endX,endY), (0,255,0), 2)
			# cv2.rectangle(mhi_frame,(startX, startY), (endX,endY), (0,255,0), 1)
			# construct a dlib rectangle object from the bounding
			# box coordinates and then start the dlib correlation
			# tracker
			tracker = dlib.correlation_tracker()
			rect = dlib.rectangle(startX, startY, endX, endY)
			tracker.start_track(rgb, rect)

			# add the tracker to our list of trackers so we can
			# utilize it during skip frames
			trackers.append(tracker)

	# otherwise, we should utilize our object *trackers* rather than
	# object *detectors* to obtain a higher frame processing throughput
	else:
		# loop over the trackers
		for tracker in trackers:
			# set the status of our system to be 'tracking' rather
			# than 'waiting' or 'detecting'
			status = "Tracking"

			# update the tracker and grab the updated position
			tracker.update(rgb)
			pos = tracker.get_position()

			# unpack the position object
			startX = int(pos.left())
			startY = int(pos.top())
			endX = int(pos.right())
			endY = int(pos.bottom())

			# add the bounding box coordinates to the rectangles list
			rects.append((startX, startY, endX, endY))
			cv2.rectangle(frame_copy,(startX, startY), (endX,endY), (0,255,0), 2)
			# cv2.rectangle(mhi_frame,(startX, startY), (endX,endY), (0,255,0), 1)

	# draw a horizontal line in the center of the frame -- once an
	# object crosses this line we will determine whether they were
	# moving 'up' or 'down'
	# cv2.line(frame, (0, H // 2), (W, H // 2), (0, 255, 255), 2)
	
	# use the centroid tracker to associate the (1) old object
	# centroids with (2) the newly computed object centroids
	objects = ct.update(rects)

	# loop over the tracked objects
	for (objectID, centroid_rect) in objects.items():
		# check to see if a trackable object exists for the current
		# object ID
		to = trackableObjects.get(objectID, None)

		# if there is no existing trackable object, create one
		if to is None:
			to = TrackableObject(objectID, centroid_rect[0], MHI_NUM_FRAMES)

		centroid = centroid_rect[0]
		startX = centroid_rect[1][0]
		startY = centroid_rect[1][1]
		endX = centroid_rect[1][2]
		endY = centroid_rect[1][3]

		to.bbqueue.enqueue(np.array([[startX,startY], [endX,endY], [startX,endY], [endX,startY]]))
		to.boudingbox()

		b_x,b_y,b_w,b_h = to.bb
		cv2.rectangle(mhi_frame,(b_x, b_y), (b_x+b_w,b_y+b_h), (0,255,0), 3)

		# print(to.bb)
		# # otherwise, there is a trackable object so we can utilize it
		# # to determine direction
		# else:
		# 	# the difference between the y-coordinate of the *current*
		# 	# centroid and the mean of *previous* centroids will tell
		# 	# us in which direction the object is moving (negative for
		# 	# 'up' and positive for 'down')
		# 	y = [c[1] for c in to.centroids]
		# 	direction = centroid[1] - np.mean(y)
		# 	to.centroids.append(centroid)
		#
		# 	# check to see if the object has been counted or not
		# 	if not to.counted:
		# 		# if the direction is negative (indicating the object
		# 		# is moving up) AND the centroid is above the center
		# 		# line, count the object
		# 		if direction < 0 and centroid[1] < H // 2:
		# 			totalUp += 1
		# 			to.counted = True
		#
		# 		# if the direction is positive (indicating the object
		# 		# is moving down) AND the centroid is below the
		# 		# center line, count the object
		# 		elif direction > 0 and centroid[1] > H // 2:
		# 			totalDown += 1
		# 			to.counted = True

		# store the trackable object in our dictionary
		trackableObjects[objectID] = to

		# draw both the ID of the object and the centroid of the
		# object on the output frame
		text = "ID {}".format(objectID)
		cv2.putText(frame_copy, text, (centroid[0] - 10, centroid[1] - 10),
			cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
		cv2.circle(frame_copy, (centroid[0], centroid[1]), 2, (0, 255, 0), -1)
		cv2.putText(mhi_frame, text, (centroid[0] - 10, centroid[1] - 10),
			cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
		cv2.circle(mhi_frame, (centroid[0], centroid[1]), 1, (0, 255, 0), -1)

	# construct a tuple of information we will be displaying on the
	# frame
	# info = [
	# 	("Up", totalUp),
	# 	("Down", totalDown),
	# 	("Status", status),
	# ]
	#
	# # loop over the info tuples and draw them on our frame
	# for (i, (k, v)) in enumerate(info):
	# 	text = "{}: {}".format(k, v)
	# 	cv2.putText(frame, text, (10, H - ((i * 20) + 20)),
	# 		cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

	# check to see if we should write the frame to disk
	if writer is not None:
		writer.write(frame)

	# show the output frame
	cv2.imshow("Frame", frame_copy)
	cv2.imshow("MHI_Frame", mhi_frame)
	key = cv2.waitKey(1) & 0xFF

	# if the `q` key was pressed, break from the loop
	if key == ord("q"):
		break

	# increment the total number of frames processed thus far and
	# then update the FPS counter
	totalFrames += 1
	fps.update()

# stop the timer and display FPS information
fps.stop()
print("[INFO] elapsed time: {:.2f}".format(fps.elapsed()))
print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))

# check to see if we need to release the video writer pointer
if writer is not None:
	writer.release()

# if we are not using a video file, stop the camera video stream
if not args.get("input", False):
	vs.stop()

# otherwise, release the video file pointer
else:
	vs.release()

# close any open windows
cv2.destroyAllWindows()