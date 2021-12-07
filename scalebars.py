import Metashape, math, sys, yaml, time
import numpy as np

class Scalebars_():

	def __init__(self, config_path):

		with open(config_path, 'r') as f:
			pars = yaml.load(f, Loader=yaml.SafeLoader)

		doc = Metashape.app.document

		self.chunk = doc.chunks[int(pars['chunk_id'])]
		self.ACCURACY = float(pars['accuracy'])
		self.planes = pars['planes']
		self.markers_on_planes = {}

	def clear_previous_crs(self,):
		self.chunk.crs = None
		self.chunk.transform.matrix = None
		self.chunk.remove(self.chunk.scalebars)

	def create_markers_dict(self,):
		
		for plane_key in list(self.planes.keys()):
			plane = self.planes[plane_key]
			markers_on_plane = []
			
			for marker in self.chunk.markers:
				if int(marker.label.split(' ')[1]) in list(plane.keys()):
					markers_on_plane.append(marker)
				else:
					pass
			
			self.markers_on_planes[plane_key] = markers_on_plane

	def setup_(self,):
		
		self.clear_previous_crs()
		
		self.create_markers_dict()

	def add_scalebars(self,):
		
		for plane_key in list(self.planes.keys()):
			plane = self.planes[plane_key]
			markers_on_plane = self.markers_on_planes[plane_key]

			k = 0
			for t, marker in enumerate(markers_on_plane):
				for second_marker in markers_on_plane[t+1:]:
					new_scalebar = self.chunk.addScalebar(marker, second_marker)
					p = plane[int(marker.label.split(' ')[1])]
					q = plane[int(second_marker.label.split(' ')[1])]
					new_scalebar.reference.distance = math.sqrt(sum((px - qx) ** 2.0 for px, qx in zip(p, q)))/1000
					new_scalebar.reference.accuracy = self.ACCURACY
					if k%2 == 0:
						new_scalebar.reference.enabled = True
					else:
						new_scalebar.reference.enabled = False
					k += 1

	def update_transform(self,):
		self.chunk.updateTransform()
		self.T = self.chunk.transform.matrix
		self.crs = self.chunk.crs
		self.scalebars_dict = {self.chunk.scalebars[i].label: self.chunk.scalebars[i] for i in range(len(self.chunk.scalebars))}
		self.list_errors_control = []
		self.list_errors_check = []

	def compute_marker_position(self, position):
		return self.crs.project(self.T.mulp(position))

	def compute_error(self,):
		for plane_key in list(self.planes.keys()):
			plane = self.planes[plane_key]
			markers_on_plane = self.markers_on_planes[plane_key]

			for t, marker in enumerate(markers_on_plane):
				for second_marker in markers_on_plane[t+1:]:
					p = plane[int(marker.label.split(' ')[1])]
					q = plane[int(second_marker.label.split(' ')[1])]

					pq_distance_theor = math.sqrt(sum((px - qx) ** 2.0 for px, qx in zip(p, q)))/1000

					coord_p = self.compute_marker_position(marker.position)
					coord_q = self.compute_marker_position(second_marker.position) 

					pq_distance_comp = coord_p - coord_q
					pq_distance_comp = pq_distance_comp.norm()

					error = pq_distance_theor - pq_distance_comp

					if self.scalebars_dict[f'point {marker.label.split(" ")[1]}_point {second_marker.label.split(" ")[1]}'].reference.enabled:
						self.list_errors_control.append(error)
					else:
						self.list_errors_check.append(error)

	def compute_RSME(self,list_errors):
		return(round(np.sqrt(np.mean(np.array(list_errors)**2)), 6))

	def write_results(self,):
		with open('./Statistics_scalebars.txt', 'w') as f:
			f.write('RMSE error control bars: {:.6f} m\n'.format(self.compute_RSME(self.list_errors_control)))
			f.write('RMSE error check bars: {:.6f} m'.format(self.compute_RSME(self.list_errors_check)))

	def __call__(self,):
		
		self.setup_()
		
		self.add_scalebars()

		self.update_transform()

		self.compute_error()

		self.write_results()

if __name__ == '__main__':

	start_time = time.time()

	config_path = sys.argv[1]
	sc = Scalebars_(config_path)
	sc()

	end_time = time.time()
	elapsed_time = end_time - start_time
	print('Elapsed time: {:.2f} s'.format(elapsed_time))