import Metashape, math, sys, yaml, time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
import pandas as pd

def extract_parameters_from_yaml(config_path):
	
	with open(config_path, 'r') as f:
		pars = yaml.load(f, Loader=yaml.SafeLoader)

	planes = pars['planes']
	max_num_scalebars = max([int(len(planes[key])*(len(planes[key]) - 1)/4) for key in list(planes.keys())])

	return int(pars['chunk_id']), float(pars['accuracy']), int(pars['iterations']), planes, max_num_scalebars, pars['output_savepath']


def plot_test(max_num_scalebars, output_savepath, iterations):
	df = pd.read_csv(output_savepath, header=None)
	
	means_control = [np.mean(df[df[1]==i][3]*1000) for i in range(1,int(max_num_scalebars) + 1)]
	means_check = [np.mean(df[df[1]==i][4]*1000) for i in range(1,int(max_num_scalebars) + 1)]
	std_dev_control = [np.std(df[df[1]==i][3]*1000) for i in range(1,int(max_num_scalebars) + 1)]
	std_dev_check = [np.std(df[df[1]==i][4]*1000) for i in range(1,int(max_num_scalebars) + 1)]

	num_scalebars = sorted(list(np.array(list(set(df[2])))))

	dict_bars = {'control': [means_control, std_dev_control, 'maroon', 'indianred'], 'check': [means_check, std_dev_check, 'darkgreen', 'forestgreen']}

	for bar_ in ['control', 'check']:
		fig, ax = plt.subplots(figsize = (10,10))
		means, std_dev, color, ecolor = dict_bars[bar_]
		ax.errorbar(num_scalebars, means, std_dev, linestyle='--', color = color, marker='o', markersize = 7, ecolor = ecolor)
		ax.grid(which = 'both')
		ax.set_xlabel(f'Number of scale bars [-]', fontsize = 15)
		ax.set_ylabel('RMSE [mm]', fontsize = 15)
		ax.yaxis.set_major_formatter(FormatStrFormatter('% 1.3f'))
		plt.savefig(f'./{bar_}_{str(iterations)}_{str(max_num_scalebars)}.png')
		plt.close()


class Scalebars_():

	def __init__(self, config_path, n_s = 1, it = 0):

		chunk_id, self.ACCURACY, _, self.planes, _, self.output_savepath = extract_parameters_from_yaml(config_path)

		doc = Metashape.app.document

		self.n_s = n_s
		self.it = it
		self.chunk = doc.chunks[chunk_id]
		self.num_scalebars_per_plane = {key: int(len(self.planes[key])*(len(self.planes[key]) - 1)/4) for key in list(self.planes.keys())}
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

	def select_scalebars(self,):
		ids_control = []
		ids_check = []
		for plane_key in list(self.planes.keys()):
			
			plane = self.planes[plane_key]

			num_previous_values = int(sum(np.array(list(self.num_scalebars_per_plane.values())[:plane_key - 1])*2))
			
			num_scalebars_per_plane = self.num_scalebars_per_plane[plane_key]

			num_scalebars_to_select = min(num_scalebars_per_plane, self.n_s)
			
			ids_control += list(np.random.choice(num_scalebars_per_plane, num_scalebars_to_select, replace = False)*2 + num_previous_values)
			ids_check += list(np.random.choice(num_scalebars_per_plane, num_scalebars_to_select, replace = False)*2 + 1 + num_previous_values)

		ids = ids_control + ids_check
		
		scalebars_to_remove = []

		for id_ in range(len(self.chunk.scalebars)):
			if id_ not in ids:
				scalebars_to_remove.append(self.chunk.scalebars[id_])
			else:
				pass

		self.chunk.remove(scalebars_to_remove)

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
					try:
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
					except:
						pass

	def compute_RSME(self,list_errors):
		return(round(np.sqrt(np.mean(np.array(list_errors)**2)), 6))

	def write_results(self,):
		with open(self.output_savepath, 'a+') as f:
			f.write(f'{str(self.it)},{str(self.n_s)},{str(len(self.scalebars_dict))},')
			f.write('{:.6f},'.format(self.compute_RSME(self.list_errors_control)))
			f.write('{:.6f}\n'.format(self.compute_RSME(self.list_errors_check)))

	def __call__(self,):
		
		self.setup_()
		
		self.add_scalebars()

		self.select_scalebars()

		self.update_transform()

		self.compute_error()

		self.write_results()


if __name__ == '__main__':

	config_path = sys.argv[1]

	_, _, iterations, _, max_num_scalebars, output_savepath = extract_parameters_from_yaml(config_path)
	
	start_time = time.time()

	for it in range(iterations):
		for num_scalebars in range(1, max_num_scalebars + 1):
			sc = Scalebars_(config_path, num_scalebars, it)
			sc()

	plot_test(max_num_scalebars, output_savepath, iterations)

	end_time = time.time()
	elapsed_time = end_time - start_time
	print('Elapsed time: {:.2f} s'.format(elapsed_time))