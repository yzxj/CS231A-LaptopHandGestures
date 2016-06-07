import numpy as np
import cv2
import win32api, win32con

PTLIST = [  (175, 200),
			(225, 200),
			(150, 220),
			(225, 240),
			(250, 260),
			(140, 280),
			(175, 300),
			(250, 300),
			(200, 320)]
BOX_SZ = 16
DIL_KERN = np.ones((5,5),np.uint8)

def br(pt):
	return (pt[0]+BOX_SZ, pt[1]+BOX_SZ)
def show_c_boxes(frame):
	for pt in PTLIST:
		cv2.rectangle(frame, pt, br(pt), (0,0,255), 2)
def dist(a, b):
	diffsumsq = 0
	for i in range(0, len(a)):
		diffsumsq += ((a[i]-b[i])**2)
	return diffsumsq**(0.5)
# Mean is badly affected by outliers.
# Can't use it to discard outliers.
def get_mean(mlist):
	count = 1
	msum = list(mlist[0])
	for i in range(1,len(mlist)):
		curr = mlist[i]
		for j in range(0,len(curr)):
			msum[j] += curr[j]
		count += 1
	for k in range(0,len(msum)):
		msum[k] /= float(count)
	return msum
def calibrate(frame):
	smoothened = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
	smoothened = cv2.GaussianBlur(smoothened, (9,9), 0)
	smoothened = cv2.medianBlur(smoothened, 9)
	c_list = []
	for pt in PTLIST:
		box = smoothened[pt[0]:pt[0]+BOX_SZ, pt[1]:pt[1]+BOX_SZ]
		c_list.append(cv2.mean(box))
	return c_list
def segment(frame, c_list):
	smoothened = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
	smoothened = cv2.GaussianBlur(smoothened, (9,9), 0)
	smoothened = cv2.medianBlur(smoothened, 5)
	seg = []
	var_h = 6
	var_s = 40
	var_v = 40
	for m in c_list:
		lower = np.array([m[0]-var_h, m[1]-var_s, m[2]-var_v, 0])
		upper = np.array([m[0]+var_h, m[1]+var_s, m[2]+var_v, 1])
		sub = cv2.inRange(smoothened,lower,upper)
		ret,thresh = cv2.threshold(sub,127,255,cv2.THRESH_BINARY)
		thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, DIL_KERN)
		# thresh = cv2.GaussianBlur(thresh, (9,9),0)
		if len(seg)==0:
			seg = thresh
		else:
			seg = cv2.add(seg, thresh)
	cv2.imshow('frame', seg)
	cv2.waitKey(99999)
def mouse_shift(x,y):
	win32api.mouse_event(win32con.MOUSEEVENTF_MOVE,x,y)
	# win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, \
	# 					int(x/SCREEN_WIDTH*65535.0), int(y/SCREEN_HEIGHT*65535.0))
def click():
    cx, cy = win32api.GetCursorPos() 
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN,cx,cy,0,0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,cx,cy,0,0)
def detect(frame):
	cp = np.copy(frame)
	contours, hierarchy = cv2.findContours(cp,cv2.RETR_TREE,cv2.CHAIN_APPROX_TC89_L1)
	max_area = 0
	if len(contours)>0:
		ci = 0
		for i in range(len(contours)):
			cnt=contours[i]
			area = cv2.contourArea(cnt)
			if(area>max_area):
				max_area=area
				ci=i
		cnt=contours[ci]
		defects = []
		hull = cv2.convexHull(cnt,returnPoints = False)
		if (len(hull)>3 and len(cnt)>3):
			defects = cv2.convexityDefects(cnt,hull)
			M = cv2.moments(cnt)
			cent_x = int(M['m10']/M['m00'])
			cent_y = int(M['m01']/M['m00'])
			if len(defects)>0:
				for i in range(defects.shape[0]):
					s,e,f,d = defects[i,0]
					start = tuple(cnt[s][0])
					end = tuple(cnt[e][0])
					far = tuple(cnt[f][0])
					cv2.line(frame,start,end,[0,255,0],2)
					cv2.circle(frame,far,5,[0,0,255],-1)
				cv2.imshow('cvhull', frame)
				cv2.waitKey(99999)
		return (cent_x, cent_y), len(defects)
	return (0,0), 0

###------- Main Function -------###
if __name__ == '__main__':
	# Note: to use laptop native camera, change 1 to 0
	cap = cv2.VideoCapture(1)
	# cap = cv2.VideoCapture(1)
	# print "Reading from usb camera..."
	# print "For calibration, cover all the red boxes with your hand and press 'c'."
	# cap = cv2.VideoCapture('data/final (2).mp4')

	fgbg = cv2.BackgroundSubtractorMOG()

	open_tries = 0
	calibrated = False
	calibrating = False
	detected = False
	centre = [0,0]
	n_vert = 0
	cmd_delay_count = 0
	cmd_delay_max = 10
	c_list = []

	# Main loop
	while(True):
		# Capture frame-by-frame
		ret, frame = cap.read()
		# It takes a while for my camera to load
		while frame is None and open_tries<10:
			open_tries += 1
			cv2.waitKey(100)
			ret, frame = cap.read()

		# For Background subtraction
		frame = fgbg.apply(frame)
		frame = cv2.morphologyEx(frame, cv2.MORPH_CLOSE, DIL_KERN)
		frame = cv2.medianBlur(frame, 5)

		# There's a hierachy of stages:
		# Calibrated ....-> Detected     -> Gesture detection
		# 			    '-> Not Detected -> Hand detection
		# Not Calibrated -> Wait for calibration signal
		# if calibrated:
			# frame = segment(frame, c_list)
			# break # TODO: REMOVE
		if detected:
			if cmd_delay_count == 0:
				# Adjust cursor based on shift
				new_centre,num_vert = detect(frame)
				print new_centre, num_vert
				# Check if there is a hand
				if num_vert==0:
					detected = False
				# If number of fingers shown fall, click
				elif num_vert < n_vert:
					click()
					cmd_delay_count = cmd_delay_max
					print 'Clicked!'
				# Normal movement = move cursor
				else:
					shiftx = new_centre[0] - centre[0]
					shifty = new_centre[1] - centre[1]
					mouse_shift((-1)*shiftx, shifty)
				centre = new_centre
				n_vert = num_vert
			else:
				# cmd_delay gives a lag time between clicks
				cmd_delay_count -= 1
		else:
			new_centre, new_vert = detect(frame)
			if new_centre is not None and new_vert>=4:
				centre = new_centre
				n_vert = new_vert
				cmd_delay_count = 0
				detected = True
		# else:
		# 	if calibrating:
		# 		c_list = calibrate(frame)
		# 		calibrated = True
		# 		calibrating = False
		# 	else:
		# 		show_c_boxes(frame)
				
		# Display the resulting frame
		cv2.imshow('Gesture Detector',frame)
		keyIn = cv2.waitKey(1)
		if keyIn & 0xFF == ord('q'):
			break
		# if (not calibrated) and (keyIn & 0xFF == ord('c')):
		# 	calibrating = True

	# When everything done, release the capture
	cap.release()
	cv2.destroyAllWindows()