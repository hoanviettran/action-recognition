from bbqueue import BoundingBoxesQueue
import cv2

class TrackableObject:
	def __init__(self, objectID, centroid, mhi_num_frames):
		# store the object ID, then initialize a list of centroids
		# using the current centroid
		self.objectID = objectID
		self.centroids = [centroid]
		self.bbqueue = BoundingBoxesQueue(mhi_num_frames)
		# initialize a boolean used to indicate if the object has
		# already been counted or not
		self.counted = False
		self.bb = []

	def boudingbox(self):
		self.bb = cv2.boundingRect(self.bbqueue.concatenate())
	
