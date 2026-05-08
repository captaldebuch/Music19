import networkx as nx
import os

def load_graph(path):
    if not os.path.exists(path):
        print(f"Graph file {path} not found. Run graph_builder.py first.")
        return None
    return nx.read_graphml(path)

def retrieve_subgraph_context(G, query_term, depth=2):
    """
    Retrieve neighboring nodes up to a certain depth for a query term.
    """
    query_term = query_term.lower()
    
    if query_term not in G.nodes():
        print(f"Term '{query_term}' not found in the Knowledge Graph.")
        return None
        
    # Get ego graph (subgraph of neighbors up to 'depth')
    subgraph = nx.ego_graph(G, query_term, radius=depth)
    
    context = []
    context.append(f"Graph Context for '{query_term}':")
    
    # Simple formatting of relations
    for u, v, data in subgraph.edges(data=True):
        relation = data.get('relation', 'connected_to')
        context.append(f"- {u} {relation} {v}")
        
    return "\n".join(context)

def generate_response(query, context):
    """
    Simulated LLM response generation based on Graph Context.
    """
    if not context:
        return f"I cannot answer questions about '{query}' as it is not in the knowledge graph."
        
    response = f"Based on the Knowledge Graph, here is what I know about '{query}':\n\n"
    response += context
    response += "\n\n(This is a simulated GraphRAG response.)"
    return response

def main():
    print("--- Starting GraphRAG System ---")
    G = load_graph("graphs/performance_graph.graphml")
    
    if G:
        queries = ["rebec", "troubadour", "dance"]
        for query in queries:
            print(f"\nQuerying: {query}")
            context = retrieve_subgraph_context(G, query)
            response = generate_response(query, context)
            print(response)

if __name__ == "__main__":
    main()
