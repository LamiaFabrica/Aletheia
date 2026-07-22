import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

PILLARS = [
    "Topology", "Probability", "Ontology", "Teleology",
    "Graph", "Dataset", "Dimensionality", "Human Anomaly"
]

def generate_lingua_mandala(floats, filepath):
    """
    Renders an 8-float Lingua Geometry into a distinct radial mandala.
    Args:
        floats (list/ndarray): Array of exactly 8 float values (ideally normalized between 0 and 1, or -1 and 1).
        filepath (str): Output path for the .png image.
    """
    assert len(floats) == 8, "Lingua geometry must have exactly 8 dimensions."
    
    # Normalize values for plotting (assuming rough EBB range)
    # The absolute value can act as magnitude, sign can act as color
    magnitudes = np.abs(floats)
    # Ensure they are visible
    magnitudes = np.clip(magnitudes, 0.1, 1.0)
    
    # Setup polar plot
    N = 8
    theta = np.linspace(0.0, 2 * np.pi, N, endpoint=False)
    width = (2*np.pi) / N

    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw={'projection': 'polar'})
    
    # Color map based on value (positive = teal/blue, negative = orange/red)
    colors = plt.cm.coolwarm((np.array(floats) + 1) / 2.0)

    bars = ax.bar(theta, magnitudes, width=width, bottom=0.0, color=colors, alpha=0.9, edgecolor='black')

    # Remove labels and grids for a pure mathematical symbol
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['polar'].set_visible(False)
    
    plt.tight_layout()
    plt.savefig(filepath, dpi=64, bbox_inches='tight', pad_inches=0, transparent=True)
    plt.close(fig)

if __name__ == "__main__":
    # Test rendering
    test_floats = [0.9, -0.8, 0.5, 0.2, -0.4, 0.8, -0.1, 0.7]
    generate_lingua_mandala(test_floats, "test_mandala.png")
    print("Test mandala rendered to test_mandala.png")
