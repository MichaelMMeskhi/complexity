# Necessities
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Sklearn imports (models, synthetic data, etc...)
from sklearn.datasets import make_moons
from sklearn.datasets import make_gaussian_quantiles
from sklearn.manifold.t_sne import TSNE
from sklearn.svm import SVC
from sklearn.naive_bayes import GaussianNB
from sklearn.tree import DecisionTreeClassifier
from sklearn.neural_network import MLPClassifier

# Active Learning and Complexity Modules
import modules.util as u
from modules.oracle import Oracle
import modules.complexity_estimator as ce
from nd_boundary_plot.plots import nd_boundary_plot
from modules.active_da import CADA

# Data pre-processing and import
# from modules import mnist
from modules import mnist 

####################################################

'''
    Scatter plot for the dataset

'''
def plot_ds(grid_size, loc, X, y, xx, yy, title, seeds=None, colspan=1, rowspan=1):
    ax = plt.subplot2grid(grid_size, loc, rowspan=rowspan, colspan=colspan)
    ax.set_title(title)

    # Plot the training points
    ax.scatter(X[:, 0],X[:, 1], c=y)

    # Plot the seeds
    if seeds is not None:
        ax.scatter(X[seeds, 0], X[seeds, 1], alpha=1.0, facecolors='magenta')

    ax.set_xlim(xx.min(), xx.max())
    ax.set_ylim(yy.min(), yy.max())
    ax.set_xticks(())
    ax.set_yticks(())

'''
    Perform Active Learning
    QueryStrategy (Random Sampling or Uncertainty Sampling)

'''

def active(classifiers, datasets, experiments, query_strat, quota=25, plot_every_n=5):
    for dataset_index, ((X_src, y_src), (X_tgt, y_tgt)) in enumerate(datasets):
        u_tgt = [None] * len(X_tgt)
        est_src = ce.ComplexityEstimator(X_src, y_src, n_windows=10, nK=10)
        est_tgt = ce.ComplexityEstimator(X_tgt, y_tgt, n_windows=10, nK=10)

        # Declare Dataset instance, X is the feature, y is the label (None if unlabeled)
        X = np.vstack((X_src, X_tgt))

        if X.shape[1] > 2:
            X_src_plt = TSNE().fit_transform(X_src)
            X_tgt_plt = TSNE().fit_transform(X_tgt)
            X_plt = np.vstack((X_src_plt, X_tgt_plt))
        elif X.shape[1] == 2:
            X_src_plt = X_src
            X_tgt_plt = X_tgt
            X_plt = X
        else:
            raise AttributeError

        h = .05  # Step size in the mesh
        x_min, x_max = X_plt[:, 0].min() - h, X_plt[:, 0].max() + h
        y_min, y_max = X_plt[:, 1].min() - h, X_plt[:, 1].max() + h
        xx, yy = np.meshgrid(np.arange(x_min, x_max, h), np.arange(y_min, y_max, h))
        figure = plt.figure(figsize=(27, 13))
        grid_size = (1+len(classifiers), 6)

        for classifier_index, classifier in enumerate(classifiers):
            model = classifier
            oracle = Oracle(X_tgt, y_tgt)

            # Plot source dataset
            plot_ds(grid_size, (0, 0), X_src_plt, y_src, xx, yy, 'Source', est_src.seeds)
            ax = plt.subplot2grid(grid_size, (0,1), colspan=2)
            ax.set_title('Source complexity')
            Ks, Es = est_src.get_k_complexity()
            ax.plot(Ks, Es)
            ax.set_xlabel('AUC=' + ('%.2f' % est_src.auc()).lstrip('0'))

            # Plot target dataset
            plot_ds(grid_size, (0, 3), X_tgt_plt, y_tgt, xx, yy, 'Target', est_tgt.seeds)
            ax = plt.subplot2grid(grid_size, (0,4), colspan=2)
            Ks, Es = est_tgt.get_k_complexity()
            ax.set_title('Target complexity')
            ax.plot(Ks, Es)
            ax.set_xlabel('AUC=' + ('%.2f' % est_tgt.auc()).lstrip('0'))
            w = 0
            X_known = X_src.tolist()
            y_known = y_src.tolist()

            for i in range(quota):  # Loop through the number of queries

                if query_strat == 'RandomSampling' :
                    loc, y_loc = oracle.random_query()  # Sample target using RandomSampling strategy
                    u_tgt[loc] = y_loc
                    X_known.append(X_tgt[loc])
                    y_known.append(y_tgt[loc])

                    if i == 0 or i % plot_every_n == 0 or i == quota - 1:
                        model.fit(X_known, y_known)  # Train model with newly-updated dataset
                        score = model.score(X_tgt, y_tgt)
                        y_predicted = model.predict(X_tgt)
                        ax = plt.subplot2grid(grid_size, (classifier_index + 1, w))
                        nd_boundary_plot(X_tgt, y_predicted, model, ax)

                        if i == 0:
                            ax.set_ylabel(u.classname(model))

                        if classifier_index == 0:
                            ax.set_title('# Queries=' + str(i))

                        ax.set_xlabel('Accuracy='+('%.2f' % score).lstrip('0'))
                        w += 1

                elif query_strat == 'UncertaintySampling':
                    model.fit(X_known, y_known) # Fit model on source only to predict probabilities
                    loc, X_chosen = oracle.uncertainty_sampling(model) # Sample target using UncertaintySampling strategy
                    X_known.append(X_tgt[loc])
                    y_known.append(y_tgt[loc])

                    if i == 0 or i % plot_every_n == 0 or i == quota - 1:
                        model.fit(X_known, y_known)  # Train model with newly-updated dataset
                        score = model.score(X_tgt, y_tgt)
                        y_predicted = model.predict(X_tgt)
                        ax = plt.subplot2grid(grid_size, (classifier_index + 1, w))
                        nd_boundary_plot(X_tgt, y_predicted, model, ax)

                        if i == 0:
                            ax.set_ylabel(u.classname(model))

                        if classifier_index == 0:
                            ax.set_title('# Queries=' + str(i))

                        ax.set_xlabel('Accuracy='+('%.2f' % score).lstrip('0'))
                        w += 1

        figure.suptitle(experiments[dataset_index] + query_strat )
        figure.tight_layout()
        fname = './vis/' + str(experiments[dataset_index] + query_strat ) + '.png'
        figure.savefig(fname)

    plt.tight_layout()
    plt.show()

def bsda_active(datasets=[], baseline_clf=SVC(), N=100):
	for ((X_src, y_src), (X_tgt, y_tgt)) in datasets:
		X_src, y_src = X_src, y_src
		X_tgt, y_tgt = X_tgt, y_tgt

	CADA_clf = CADA(X_src, y_src)
	ixs = CADA_clf.query(X_tgt, N)
	BSDA_X_Train, BSDA_y_Train = X_tgt[ixs], y_tgt[ixs]
	baseline_clf.fit(BSDA_X_Train, BSDA_y_Train)
	print(baseline_clf.predict(X_tgt[-ixs]))
	


def main():
    #baseline_clfs = [SVC(), GaussianNB(), DecisionTreeClassifier(), MLPClassifier(hidden_layer_sizes=(10,10,10,10,10,10), solver='lbfgs', alpha=2, random_state=1, activation='relu')]
    datasets = []
    experiments = []
    query_strat = 'RandomSampling'

    # datasets.append((make_gaussian_quantiles(n_samples=500, n_features=10, n_classes=2), 
    #                  make_gaussian_quantiles(n_samples=500, n_features=10, n_classes=2)))
    # experiments.append('hastie_10_2_vs_gauss_quant_10_2')
    # datasets.append((make_moons(n_samples=1000), make_moons(n_samples=1000)))

    # experiments.append('moons')
    # datasets.append((u.hastie(1000), u.hastie(1000)))

    datasets.append((make_gaussian_quantiles(n_samples=500, n_features=5, n_classes=3),
                     make_gaussian_quantiles(n_samples=500, n_features=5, n_classes=3)))
    experiments.append('gauus')

    #datasets.append((mnist.load_mnist(), mnist.load_mnist_rotated()))
    #experiments.append('MNIST_vs_MNIST_Rotated')

    #baseline_active(classifiers=clfs, datasets=datasets, experiments=experiments, query_strat=query_strat)
    bsda_active(datasets=datasets)

if __name__ == "__main__":
    main()
