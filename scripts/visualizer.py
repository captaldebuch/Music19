import os
import networkx as nx
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Note: In a real environment, PyVis and GeoPandas would be used.
# Since this is a setup/baseline DH script, we provide the template.

def create_pyvis_graph(graph_path, output_dir):
    """
    Creates an interactive PyVis HTML export of the knowledge graph.
    """
    print("--- Creating Interactive Semantic Network ---")
    if not os.path.exists(graph_path):
        print("Graph not found.")
        return
        
    try:
        from pyvis.network import Network
        G = nx.read_graphml(graph_path)
        net = Network(notebook=False, height="750px", width="100%", bgcolor="#222222", font_color="white")
        net.from_nx(G)
        out_path = os.path.join(output_dir, "semantic_network_interactive.html")
        net.save_graph(out_path)
        print(f"Saved PyVis interactive graph to {out_path}")
    except ImportError:
        print("PyVis not installed. Creating a dummy HTML export for the pipeline.")
        out_path = os.path.join(output_dir, "semantic_network_interactive.html")
        with open(out_path, 'w') as f:
            f.write("<html><body><h1>Interactive Semantic Network (PyVis Template)</h1></body></html>")
        print(f"Saved placeholder PyVis interactive graph to {out_path}")

def create_geographic_map(dataset_path, output_dir):
    """
    Simulates using Geopandas to map the diffusion of instruments.
    """
    print("--- Creating Geographic Map ---")
    # For a real project:
    # import geopandas as gpd
    # world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
    # ... plotting logic ...
    
    out_path = os.path.join(output_dir, "geographic_diffusion.html")
    with open(out_path, 'w') as f:
        f.write("<html><body><h1>Geographic Diffusion Map (Geopandas/Folium Template)</h1></body></html>")
    print(f"Saved placeholder Geographic Map to {out_path}")

def create_topic_evolution(dataset_path, output_dir):
    """
    Generates streamgraphs showing the rise and fall of musical concepts between 500 and 1500.
    Using matplotlib stackplot as a baseline.
    """
    print("--- Creating Topic Evolution Streamgraph ---")
    # Simulated data for Medieval Period (500 - 1500)
    years = np.arange(500, 1501, 100)
    
    # Fake frequencies for topics
    chant = [10, 20, 30, 50, 80, 100, 90, 80, 70, 60, 50]
    polyphony = [0, 0, 0, 0, 5, 10, 30, 60, 90, 120, 150]
    troubadour = [0, 0, 0, 0, 0, 10, 50, 80, 40, 10, 0]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.stackplot(years, chant, polyphony, troubadour, labels=['Gregorian Chant', 'Polyphony', 'Troubadour Songs'])
    ax.set_title('Evolution of Musical Concepts (500-1500)')
    ax.set_ylabel('Frequency in Texts')
    ax.set_xlabel('Year')
    ax.legend(loc='upper left')
    
    out_path = os.path.join(output_dir, "topic_evolution.png")
    plt.savefig(out_path)
    plt.close()
    print(f"Saved Topic Evolution Streamgraph to {out_path}")

def main():
    os.makedirs('visualizations', exist_ok=True)
    graph_path = "graphs/performance_graph.graphml"
    dataset_path = "datasets/master_performance_dataset.csv"
    
    create_pyvis_graph(graph_path, 'visualizations')
    create_geographic_map(dataset_path, 'visualizations')
    create_topic_evolution(dataset_path, 'visualizations')

if __name__ == "__main__":
    main()
