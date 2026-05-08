import pandas as pd
import networkx as nx
import json
import os
import re

def extract_geo_temporal(text, publication_year):
    """
    Extract naive geographic references and default to publication year for temporal edge.
    """
    geo_nodes = []
    text_lower = str(text).lower()
    
    # Naive geographic extraction
    if 'france' in text_lower or 'french' in text_lower or 'paris' in text_lower: geo_nodes.append('France')
    if 'italy' in text_lower or 'italian' in text_lower or 'rome' in text_lower: geo_nodes.append('Italy')
    if 'germany' in text_lower or 'german' in text_lower or 'berlin' in text_lower: geo_nodes.append('Germany')
    if 'spain' in text_lower or 'spanish' in text_lower or 'madrid' in text_lower: geo_nodes.append('Spain')
    if 'russia' in text_lower or 'russian' in text_lower or 'moscow' in text_lower: geo_nodes.append('Russia')
    if 'england' in text_lower or 'english' in text_lower or 'london' in text_lower: geo_nodes.append('England')

    return geo_nodes, publication_year

def build_knowledge_graph(df, taxonomy):
    """
    Build a semantic graph where nodes are terms, categories, geography, and time.
    """
    G = nx.Graph()
    
    print("Adding nodes and edges from taxonomy...")
    for category, terms in taxonomy['categories'].items():
        G.add_node(category, type='category', color='red')
        if isinstance(terms, list):
            for term in terms:
                G.add_node(term, type='term', color='blue')
                G.add_edge(category, term, relation='contains')
        elif isinstance(terms, dict):
            for subcat, subterms in terms.items():
                G.add_node(subcat, type='subcategory', color='orange')
                G.add_edge(category, subcat, relation='contains')
                for term in subterms:
                    G.add_node(term, type='term', color='blue')
                    G.add_edge(subcat, term, relation='contains')

    print("Extracting co-occurrences from dataset...")
    # Filter for performance-related entries
    perf_df = df[df['category'] != 'GENERAL'].head(1000) # Sample for speed
    
    for _, row in perf_df.iterrows():
        headword = str(row['headword']).lower()
        if headword == 'nan': continue
        cat = str(row['category'])
        subcat = str(row['subcategory'])
        
        # Add headword as node
        G.add_node(headword, type='headword', color='green')
        # Link to its category
        if cat in G:
            G.add_edge(headword, cat, relation='belongs_to')
            
        # Extract Geo and Temporal edges
        definition = str(row['definition'])
        pub_year = row.get('publication_year', 'Unknown')
        geo_nodes, time_node = extract_geo_temporal(definition, pub_year)
        
        # Temporal Edge
        if time_node != 'Unknown':
            time_str = f"Year_{time_node}"
            G.add_node(time_str, type='temporal', color='purple')
            G.add_edge(headword, time_str, relation='attested_in')
            
        # Geo Nodes
        for geo in geo_nodes:
            G.add_node(geo, type='geographic', color='brown')
            G.add_edge(headword, geo, relation='circulated_in')
        
        # Look for other taxonomy terms in the definition
        definition_lower = definition.lower()
        for node in G.nodes():
            if node != headword and str(node).lower() in definition_lower:
                # Limit to term-term relations for clarity
                if G.nodes[node].get('type') == 'term':
                    G.add_edge(headword, node, relation='mentions', weight=1)

    return G

def main():
    print("Loading data...")
    if not os.path.exists('datasets/master_performance_dataset_v3.csv'):
        print("Run build_dataset.py first.")
        return

    df = pd.read_csv('datasets/master_performance_dataset_v3.csv')
    with open('metadata/performance_taxonomy.json', 'r') as f:
        taxonomy = json.load(f)
    
    G = build_knowledge_graph(df, taxonomy)
    
    print(f"Graph constructed: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.")

    # Export
    os.makedirs('graphs', exist_ok=True)
    nx.write_graphml(G, "graphs/performance_graph.graphml")
    print("Saved graph to graphs/performance_graph.graphml")

    # Centrality analysis — exclude temporal and geographic helper nodes
    SKIP_TYPES = {'temporal', 'geographic'}
    semantic_nodes = [n for n, d in G.nodes(data=True) if d.get('type') not in SKIP_TYPES]
    G_semantic = G.subgraph(semantic_nodes)
    centrality = nx.degree_centrality(G_semantic)
    top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:10]

    print("\n--- Top Central Concepts (semantic subgraph, excluding temporal/geo) ---")
    with open('reports/graph_analysis.md', 'w') as f:
        f.write("# Knowledge Graph Analysis\n\n")
        f.write(f"- Nodes (full graph): {G.number_of_nodes()}\n")
        f.write(f"- Edges (full graph): {G.number_of_edges()}\n")
        f.write(f"- Nodes (semantic subgraph): {G_semantic.number_of_nodes()}\n")
        f.write(f"- Edges (semantic subgraph): {G_semantic.number_of_edges()}\n\n")
        f.write("## Top Central Concepts (Degree Centrality, semantic subgraph)\n")
        for node, val in top_nodes:
            print(f"{node}: {val:.4f}")
            f.write(f"- **{node}**: {val:.4f}\n")

if __name__ == "__main__":
    main()
