#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Everest Uriel Castaneda
@desc: File for obtaining gene-only pathways
"""

import json
import typer
import pandas as pd
import networkx as nx
from pathlib import Path
from itertools import combinations
import xml.etree.ElementTree as ET
from collections import defaultdict

app = typer.Typer()

def conv_dict(root):
    # This dictionary is the default option
    # Only compounds are unique
    entry_dict = defaultdict(list)
    for entries in root.findall('entry'):
        for key, items in entries.attrib.items():
            entry_dict[key].append(items)  
       
    entry_id=[]
    entry_name=[]
    for key, items in entry_dict.items():
        if key == 'id':
            for i in items:
                entry_id.append(i)
        if key == 'name':
            for i in items:
                entry_name.append(i)

    unique_compound = []
    for i in range(0, len(entry_id)):
        c = [name + '-' + entry_id[i] if name.startswith('cpd:') or name == 'undefined' else name for name in entry_name[i].split()]
        unique_compound.append(' '.join(c))

    conversion_dictionary = dict(zip(entry_id, unique_compound))
    return conversion_dictionary

def conv_dict_unique(root):
    # This dictionary is the unique version
    # Every item is unique to reveal subgraphs
    entry_dict = defaultdict(list)
    for entries in root.findall('entry'):
        for key, items in entries.attrib.items():
            entry_dict[key].append(items)  
       
    entry_id=[]
    entry_name=[]
    for key, items in entry_dict.items():
        if key == 'id':
            for i in items:
                entry_id.append(i)
        if key == 'name':
            for i in items:
                entry_name.append(i)
   
    unique_name = []
    for i in range(0, len(entry_id)):
        e = [name + '-' + entry_id[i] for name in entry_name[i].split()]
        unique_name.append(' '.join(e))

    conversion_dictionary = dict(zip(entry_id, unique_name))
    return conversion_dictionary

def graphics_dict(root):
    entry_dict = defaultdict(list)
    for entry in root.findall('entry'):
        for graphics in entry.find('graphics').items():
            if graphics[0] == 'x' or graphics[0] == 'y':
                entry_dict[entry.attrib['id']].append(int(graphics[1]))
    graphics_dict = {}
    for key, items in entry_dict.items():
        graphics_dict[key] = tuple(items)
    return graphics_dict

@app.command()
def file(file: typer.FileText, unique: bool = False, graphics: bool = False):
    wd = Path.cwd()
    tree = ET.parse(file)
    root = tree.getroot()
   
    title = root.get('title')
    pathway = root.get('name').replace('path:', '')
    pathway_link = root.get('link')
    if graphics:
        # Graphics
        graphics = graphics_dict(root)
        
        typer.echo(f'Now parsing: {title}...')
           
        e1 = []
        e2 = []
        n = []
        v = []
        for relation in root.findall('relation'):
            e1.append(relation.get('entry1'))
            e2.append(relation.get('entry2'))
            for subtype in relation.findall('subtype'):
                n.append(subtype.get('name'))
                v.append(subtype.get('value'))
           
        d = []
        for relation in root.findall('relation'):
            for subtype in relation:
                d1=relation.attrib
                d2=subtype.attrib
                d3=json.dumps(d1),json.dumps(d2)
                d.append(d3)    

        edgelist=[]
        # Takes json dictionary and removes formatting in order to obtain an edgelist
        # This odd line of code is necessary  because of the various nested and non-nested subtypes
        # This allows for edges to inherit weights from a nested subtype
        for line in d:
            x=line[0].replace("{","").replace("}","").replace('"entry1":',"")\
                .replace('"entry2":',"").replace('"type":',"").replace('"name":',"")\
                .replace('"value":',"").replace('"','').replace(',',"\t").replace(' ', '')
            y=line[1].replace("{","").replace("}","").replace('"name":',"")\
                .replace('"',"").replace('value:',"").replace(",",'\t').replace(' ', '')
            edgelist.append(x+"\t"+y)

        df=pd.DataFrame(edgelist)
       
        if df.empty:
            typer.echo(f'File "{file}" cannot be parsed.\nVisit {pathway_link} for pathway details.\nThere are likely no edges in which to parse...')
        else:
            df=df[0].str.split("\t", expand=True).rename({0: 'entry1',1: 'entry2',
                                                      2: 'types', 3:'name',
                                                      4: 'value'}, axis='columns')

            entry_dict = defaultdict(list)
            for entries in root.findall('entry'):
                for key, items in entries.attrib.items():
                    entry_dict[key].append(items)  
                    
            # Graphics
            df['pos1'] = df['entry1'].map(graphics)
            df['pos2'] = df['entry2'].map(graphics)
           
            entry_id=[]
            entry_name=[]
            entry_type=[]
            for key, items in entry_dict.items():
                if key == 'id':
                    for i in items:
                        entry_id.append(i)
                if key == 'name':
                    for i in items:
                        entry_name.append(i)
                if key == 'type':
                    for i in items:
                        entry_type.append(i)
            
            if unique:
                conversion_dictionary = conv_dict_unique(root)
            else:
                conversion_dictionary = conv_dict(root)
           
            df['entry1'] = df['entry1'].map(conversion_dictionary)
            df['entry2'] = df['entry2'].map(conversion_dictionary)
            df['entry1'] = df['entry1'].astype(str).str.split(' ', expand = False)
            df['entry2'] = df['entry2'].astype(str).str.split(' ', expand = False)
           
            # Parse the cliques seperate so they won't inherit neighbor weights
            # Allows for custom weights so user knows which are customly parsed
            clique_edges = []
            for index, rows in df.iterrows():
                if len(rows['entry1']) > 1:
                    cliques = [x for x in combinations(rows['entry1'], 2)]
                    cliques1 = [tup + ('type 2', 'undirectional', 'clique') for tup in cliques]
                    clique_edges.append(cliques1)
                if len(rows['entry2']) > 1:
                    cliques = [x for x in combinations(rows['entry2'], 2)]
                    cliques2 = [tup + ('type 2', 'undirectional', 'clique') for tup in cliques]
                    clique_edges.append(cliques2)
            clique2df = [e for edge in clique_edges for e in edge]
            cliquedf = pd.DataFrame.from_records(clique2df, columns = ['entry1', 'entry2', 'type', 'value', 'name'])
           
            edges = []
            for index, rows in df.iterrows():
                lists = rows['entry1'] + rows['entry2']
                # Cliques here inherit neighbor weights, but will be overwritten by above
                cliques = [x for x in combinations(lists, 2)]
                network = [tup + (rows['types'], rows['value'], rows['name'], rows['pos1'], rows['pos2']) for tup in cliques]
                edges.append(network)
            
            # This removes edges which contain +p (phosphorylation) these oftentimes
            # overwrite important weight attributes while providing no vital information
            # edges2df = [e for edge in edges for e in edge if '+p' not in e and '-p' not in e]
            
            # Standard line for obtaining a dataframe of edges
            edges2df = [e for edge in edges for e in edge]
            # Create pandas DF from edges
            df_out = pd.DataFrame.from_records(edges2df, columns = ['entry1', 'entry2', 'type', 'value', 'name', 'pos1', 'pos2'])
            
            # Graphics
            pos_dict1 = {}
            pos_dict2 = {}
            for index, rows in df_out.iterrows():
                pos_dict1[rows['entry1']] = rows['pos1']
                pos_dict2[rows['entry2']] = rows['pos2']
            pos = pos_dict1 | pos_dict2
            json_dict = json.dumps(pos)
            with open('%s_graphics.txt' % pathway, 'w') as outfile:
                outfile.write(json_dict)
            
            dft = df_out.groupby(['entry1', 'entry2'])['type'].apply(list).reset_index()
            dfv = df_out.groupby(['entry1', 'entry2'])['value'].apply(list).reset_index()
            dfn = df_out.groupby(['entry1', 'entry2'])['name'].apply(list).reset_index()
            dfx = dft
            dfx['value'] = dfv['value'].agg(','.join)
            dfx['name'] = dfn['name'].agg(','.join)
            dfx['type'] = dft['type'].agg(','.join)
            # Ensures independently parsed cliques overwrite the cliques, which inherited neighbor weights
            xdf = pd.concat([dfx, cliquedf]).drop_duplicates(subset = ['entry1', 'entry2'], keep = 'last')

            if xdf[(xdf['entry1'].str.startswith('cpd:')) | (xdf['entry2'].str.startswith('cpd:'))].empty == True and xdf[(xdf['entry1'].str.startswith('undefined')) | (xdf['entry2'].str.startswith('undefined'))].empty == True:
                # If pathway has no compounds or undefined nodes, write file
                xdf_out = xdf[(~xdf['entry1'].str.startswith('path')) & (~xdf['entry2'].str.startswith('path'))]
                xdf_out.to_csv(wd / '{}.tsv'.format(pathway), sep = '\t', index = False)
            else:
                # These next series of steps are for propagating compounds and undefined nodes
                # Uses networkx
                G = nx.from_pandas_edgelist(xdf, source = 'entry1', target = 'entry2', edge_attr = 'name', create_using = nx.DiGraph())
                new_edges = []
                for node in G.nodes:
                    # Gather roots and leaflets
                    roots = [n for n, d in G.in_degree() if d == 0]
                    leaflets = [n for n, d in G.out_degree() if d == 0]
                    # Find compounds or undefined proteins that might need propagation
                    if node.startswith('cpd') or node.startswith('undefined'):
                        if node in roots or node in leaflets:
                            # Passes root nodes and leaflet nodes
                            # These do not need propagation as they terminate
                            pass
                        else:
                            out_edges = [e for e in G.out_edges(node)]
                            in_edges = [e for e in G.in_edges(node)]
                            for i in in_edges:
                                for o in out_edges:
                                    if not i[0].startswith('cpd') and not o[1].startswith('cpd') and not i[0].startswith('undefined') and not o[1].startswith('undefined') and not i[0].startswith('path') and not o[1].startswith('path'):
                                        # Simple compound propagation removes compound between two genes
                                        # Example: hsa:xxx -> cpd:xxx -> hsa:xxx to hsa:xxx -> hsa:xxx
                                        new_edges.append([i[0], o[1], 'CPp', 'Custom', 'compound propagation'])
                                    else:
                                        # Loops through roots and leaves to find the start and end of each node that is propagated
                                        # These pathways have copious amounts of compounds and undefined genes in between the propagated genes
                                        # This loop also picks up on non-proteins that are left out if the above simple compound propagation is used
                                        for root in roots:
                                            for leaf in leaflets:
                                                if nx.has_path(G, root, node) == True and nx.has_path(G, node, leaf) == True:
                                                    # Uses the shortest path between the root/leaf and query node
                                                    rpath = [p for p in nx.shortest_path(G, root, node)]
                                                    lpath = [p for p in nx.shortest_path(G, node, leaf)]
                                                    # Skip paths that have no proteins
                                                    if all(node.startswith('cpd') or node.startswith('undefined') or node.startswith('path') for node in rpath) == True or all(node.startswith('cpd') or node.startswith('undefined') or node.startswith('path') for node in lpath) == True:
                                                        pass
                                                    else:
                                                        # Indexes all elements in the shortest path list that is a gene
                                                        rindex = [index for index, element in enumerate(rpath) if not element.startswith('cpd') and not element.startswith('undefined') and not element.startswith('path')]
                                                        lindex = [index for index, element in enumerate(lpath) if not element.startswith('cpd') and not element.startswith('undefined') and not element.startswith('path')]
                                                        # Here we use the maximum of the root path and the minimum of the leaf path to successfully propagate compounds
                                                        # Note below example
                                                        # [mmu:x, cpd:###, cpd:x] --> max is mmu:x 
                                                        # [cpd:x, cpd:###, undefined, mmu:y, mmu:###] --> min is mmu:y
                                                        # creates edge [mmu:x, mmu:y]
                                                        new_edges.append([rpath[max(rindex)], lpath[min(lindex)], 'CPp', 'Custom', 'compound propagation'])
                # Creates a dataframe of the new edges that are a result of compound propagation
                new_edges_df = pd.DataFrame(new_edges, columns = ['entry1', 'entry2', 'type', 'value', 'name'])
                # Concatenates the new edges with the edges from the above (cliques and original parsed edges)
                df0 = pd.concat([xdf, new_edges_df])
                # Drop any duplicated edges
                df1 = df0.drop_duplicates()
                # Removes compounds and undefined as they were propagated and no longer needed
                df2 = df1[(~df1['entry1'].str.startswith('cpd')) & (~df1['entry2'].str.startswith('cpd')) & (~df1['entry1'].str.startswith('undefined')) & (~df1['entry2'].str.startswith('undefined')) & (~df1['entry1'].str.startswith('path')) & (~df1['entry2'].str.startswith('path'))]
                df2.to_csv(wd / '{}.tsv'.format(pathway), sep = '\t', index = False)
    else:
        typer.echo(f'Now parsing: {title}...')
           
        e1 = []
        e2 = []
        n = []
        v = []
        for relation in root.findall('relation'):
            e1.append(relation.get('entry1'))
            e2.append(relation.get('entry2'))
            for subtype in relation.findall('subtype'):
                n.append(subtype.get('name'))
                v.append(subtype.get('value'))
           
        d = []
        for relation in root.findall('relation'):
            for subtype in relation:
                d1=relation.attrib
                d2=subtype.attrib
                d3=json.dumps(d1),json.dumps(d2)
                d.append(d3)    

        edgelist=[]
        # Takes json dictionary and removes formatting in order to obtain an edgelist
        # This odd line of code is necessary  because of the various nested and non-nested subtypes
        # This allows for edges to inherit weights from a nested subtype
        for line in d:
            x=line[0].replace("{","").replace("}","").replace('"entry1":',"")\
                .replace('"entry2":',"").replace('"type":',"").replace('"name":',"")\
                .replace('"value":',"").replace('"','').replace(',',"\t").replace(' ', '')
            y=line[1].replace("{","").replace("}","").replace('"name":',"")\
                .replace('"',"").replace('value:',"").replace(",",'\t').replace(' ', '')
            edgelist.append(x+"\t"+y)

        df=pd.DataFrame(edgelist)
       
        if df.empty:
            typer.echo(f'File "{file}" cannot be parsed.\nVisit {pathway_link} for pathway details.\nThere are likely no edges in which to parse...')
        else:
            df=df[0].str.split("\t", expand=True).rename({0: 'entry1',1: 'entry2',
                                                      2: 'types', 3:'name',
                                                      4: 'value'}, axis='columns')

            entry_dict = defaultdict(list)
            for entries in root.findall('entry'):
                for key, items in entries.attrib.items():
                    entry_dict[key].append(items)
           
            entry_id=[]
            entry_name=[]
            entry_type=[]
            for key, items in entry_dict.items():
                if key == 'id':
                    for i in items:
                        entry_id.append(i)
                if key == 'name':
                    for i in items:
                        entry_name.append(i)
                if key == 'type':
                    for i in items:
                        entry_type.append(i)
            
            if unique:
                conversion_dictionary = conv_dict_unique(root)
            else:
                conversion_dictionary = conv_dict(root)
           
            df['entry1'] = df['entry1'].map(conversion_dictionary)
            df['entry2'] = df['entry2'].map(conversion_dictionary)
            df['entry1'] = df['entry1'].astype(str).str.split(' ', expand = False)
            df['entry2'] = df['entry2'].astype(str).str.split(' ', expand = False)
           
            # Parse the cliques seperate so they won't inherit neighbor weights
            # Allows for custom weights so user knows which are customly parsed
            clique_edges = []
            for index, rows in df.iterrows():
                if len(rows['entry1']) > 1:
                    cliques = [x for x in combinations(rows['entry1'], 2)]
                    cliques1 = [tup + ('type 2', 'undirectional', 'clique') for tup in cliques]
                    clique_edges.append(cliques1)
                if len(rows['entry2']) > 1:
                    cliques = [x for x in combinations(rows['entry2'], 2)]
                    cliques2 = [tup + ('type 2', 'undirectional', 'clique') for tup in cliques]
                    clique_edges.append(cliques2)
            clique2df = [e for edge in clique_edges for e in edge]
            cliquedf = pd.DataFrame.from_records(clique2df, columns = ['entry1', 'entry2', 'type', 'value', 'name'])
           
            edges = []
            for index, rows in df.iterrows():
                lists = rows['entry1'] + rows['entry2']
                # Cliques here inherit neighbor weights, but will be overwritten by above
                cliques = [x for x in combinations(lists, 2)]
                network = [tup + (rows['types'], rows['value'], rows['name']) for tup in cliques]
                edges.append(network)
            
            # This removes edges which contain +p (phosphorylation) these oftentimes
            # overwrite important weight attributes while providing no vital information
            # edges2df = [e for edge in edges for e in edge if '+p' not in e and '-p' not in e]
            
            # Standard line for obtaining a dataframe of edges
            edges2df = [e for edge in edges for e in edge]
            # Create pandas DF from edges
            df_out = pd.DataFrame.from_records(edges2df, columns = ['entry1', 'entry2', 'type', 'value', 'name'])
            
            dft = df_out.groupby(['entry1', 'entry2'])['type'].apply(list).reset_index()
            dfv = df_out.groupby(['entry1', 'entry2'])['value'].apply(list).reset_index()
            dfn = df_out.groupby(['entry1', 'entry2'])['name'].apply(list).reset_index()
            dfx = dft
            dfx['value'] = dfv['value'].agg(','.join)
            dfx['name'] = dfn['name'].agg(','.join)
            dfx['type'] = dft['type'].agg(','.join)
            # Ensures independently parsed cliques overwrite the cliques, which inherited neighbor weights
            xdf = pd.concat([dfx, cliquedf]).drop_duplicates(subset = ['entry1', 'entry2'], keep = 'last')

            if xdf[(xdf['entry1'].str.startswith('cpd:')) | (xdf['entry2'].str.startswith('cpd:'))].empty == True and xdf[(xdf['entry1'].str.startswith('undefined')) | (xdf['entry2'].str.startswith('undefined'))].empty == True:
                # If pathway has no compounds or undefined nodes, write file
                xdf_out = xdf[(~xdf['entry1'].str.startswith('path')) & (~xdf['entry2'].str.startswith('path'))]
                xdf_out.to_csv(wd / '{}.tsv'.format(pathway), sep = '\t', index = False)
            else:
                # These next series of steps are for propagating compounds and undefined nodes
                # Uses networkx
                G = nx.from_pandas_edgelist(xdf, source = 'entry1', target = 'entry2', edge_attr = 'name', create_using = nx.DiGraph())
                new_edges = []
                for node in G.nodes:
                    # Gather roots and leaflets
                    roots = [n for n, d in G.in_degree() if d == 0]
                    leaflets = [n for n, d in G.out_degree() if d == 0]
                    # Find compounds or undefined proteins that might need propagation
                    if node.startswith('cpd') or node.startswith('undefined'):
                        if node in roots or node in leaflets:
                            # Passes root nodes and leaflet nodes
                            # These do not need propagation as they terminate
                            pass
                        else:
                            out_edges = [e for e in G.out_edges(node)]
                            in_edges = [e for e in G.in_edges(node)]
                            for i in in_edges:
                                for o in out_edges:
                                    if not i[0].startswith('cpd') and not o[1].startswith('cpd') and not i[0].startswith('undefined') and not o[1].startswith('undefined') and not i[0].startswith('path') and not o[1].startswith('path'):
                                        # Simple compound propagation removes compound between two genes
                                        # Example: hsa:xxx -> cpd:xxx -> hsa:xxx to hsa:xxx -> hsa:xxx
                                        new_edges.append([i[0], o[1], 'CPp', 'Custom', 'compound propagation'])
                                    else:
                                        # Loops through roots and leaves to find the start and end of each node that is propagated
                                        # These pathways have copious amounts of compounds and undefined genes in between the propagated genes
                                        # This loop also picks up on non-proteins that are left out if the above simple compound propagation is used
                                        for root in roots:
                                            for leaf in leaflets:
                                                if nx.has_path(G, root, node) == True and nx.has_path(G, node, leaf) == True:
                                                    # Uses the shortest path between the root/leaf and query node
                                                    rpath = [p for p in nx.shortest_path(G, root, node)]
                                                    lpath = [p for p in nx.shortest_path(G, node, leaf)]
                                                    # Skip paths that have no proteins
                                                    if all(node.startswith('cpd') or node.startswith('undefined') or node.startswith('path') for node in rpath) == True or all(node.startswith('cpd') or node.startswith('undefined') or node.startswith('path') for node in lpath) == True:
                                                        pass
                                                    else:
                                                        # Indexes all elements in the shortest path list that is a gene
                                                        rindex = [index for index, element in enumerate(rpath) if not element.startswith('cpd') and not element.startswith('undefined') and not element.startswith('path')]
                                                        lindex = [index for index, element in enumerate(lpath) if not element.startswith('cpd') and not element.startswith('undefined') and not element.startswith('path')]
                                                        # Here we use the maximum of the root path and the minimum of the leaf path to successfully propagate compounds
                                                        # Note below example
                                                        # [mmu:x, cpd:###, cpd:x] --> max is mmu:x 
                                                        # [cpd:x, cpd:###, undefined, mmu:y, mmu:###] --> min is mmu:y
                                                        # creates edge [mmu:x, mmu:y]
                                                        new_edges.append([rpath[max(rindex)], lpath[min(lindex)], 'CPp', 'Custom', 'compound propagation'])
                # Creates a dataframe of the new edges that are a result of compound propagation
                new_edges_df = pd.DataFrame(new_edges, columns = df_out.columns)
                # Concatenates the new edges with the edges from the above (cliques and original parsed edges)
                df0 = pd.concat([xdf, new_edges_df])
                # Drop any duplicated edges
                df1 = df0.drop_duplicates()
                # Removes compounds and undefined as they were propagated and no longer needed
                df2 = df1[(~df1['entry1'].str.startswith('cpd')) & (~df1['entry2'].str.startswith('cpd')) & (~df1['entry1'].str.startswith('undefined')) & (~df1['entry2'].str.startswith('undefined')) & (~df1['entry1'].str.startswith('path')) & (~df1['entry2'].str.startswith('path'))]
                df2.to_csv(wd / '{}.tsv'.format(pathway), sep = '\t', index = False)
    

    
@app.command()
def folder(fp: Path, unique: bool = False, graphics: bool = False):
    wd = Path.cwd()
    for file in Path(fp).glob('*.xml'):
        tree = ET.parse(file)
        root = tree.getroot()
   
        title = root.get('title')
        pathway = root.get('name').replace('path:', '')
        species = root.get('org')
        pathway_link = root.get('link')
        if graphics:
            # Graphics
            graphics = graphics_dict(root)
            
            output_path = wd / 'kegg_gene_network_{}'.format(species)
            output_path.mkdir(exist_ok = True)
            
            typer.echo(f'Now parsing: {title}...')
           
            e1 = []
            e2 = []
            n = []
            v = []
            for relation in root.findall('relation'):
                e1.append(relation.get('entry1'))
                e2.append(relation.get('entry2'))
                for subtype in relation.findall('subtype'):
                    n.append(subtype.get('name'))
                    v.append(subtype.get('value'))
           
            d = []
            for relation in root.findall('relation'):
                for subtype in relation:
                    d1=relation.attrib
                    d2=subtype.attrib
                    d3=json.dumps(d1),json.dumps(d2)
                    d.append(d3)    

            edgelist=[]
            # Takes json dictionary and removes formatting in order to obtain an edgelist
            # This odd line of code is necessary  because of the various nested and non-nested subtypes
            # This allows for edges to inherit weights from a nested subtype
            for line in d:
                x=line[0].replace("{","").replace("}","").replace('"entry1":',"")\
                .replace('"entry2":',"").replace('"type":',"").replace('"name":',"")\
                .replace('"value":',"").replace('"','').replace(',',"\t").replace(' ', '')
                y=line[1].replace("{","").replace("}","").replace('"name":',"")\
                .replace('"',"").replace('value:',"").replace(",",'\t').replace(' ', '')
                edgelist.append(x+"\t"+y)

            df=pd.DataFrame(edgelist)
       
            if df.empty:
                typer.echo(f'File "{file}" cannot be parsed.\nVisit {pathway_link} for pathway details.\nThere are likely no edges in which to parse...')
            else:
                df=df[0].str.split("\t", expand=True).rename({0: 'entry1',1: 'entry2',
                                                      2: 'types', 3:'name',
                                                      4: 'value'}, axis='columns')

                entry_dict = defaultdict(list)
                for entries in root.findall('entry'):
                    for key, items in entries.attrib.items():
                        entry_dict[key].append(items) 
                        
                # Graphics
                df['pos1'] = df['entry1'].map(graphics)
                df['pos2'] = df['entry2'].map(graphics)
           
                entry_id=[]
                entry_name=[]
                entry_type=[]
                for key, items in entry_dict.items():
                    if key == 'id':
                        for i in items:
                            entry_id.append(i)
                    if key == 'name':
                        for i in items:
                            entry_name.append(i)
                    if key == 'type':
                        for i in items:
                            entry_type.append(i)
                
                if unique:
                    conversion_dictionary = conv_dict_unique(root)
                else:
                    conversion_dictionary = conv_dict(root)
           
                df['entry1'] = df['entry1'].map(conversion_dictionary)
                df['entry2'] = df['entry2'].map(conversion_dictionary)
                df['entry1'] = df['entry1'].astype(str).str.split(' ', expand = False)
                df['entry2'] = df['entry2'].astype(str).str.split(' ', expand = False)
           
                # Parse the cliques seperate so they won't inherit neighbor weights
                # Allows for custom weights so user knows which are customly parsed
                clique_edges = []
                for index, rows in df.iterrows():
                    if len(rows['entry1']) > 1:
                        cliques = [x for x in combinations(rows['entry1'], 2)]
                        cliques1 = [tup + ('type 2', 'undirectional', 'clique') for tup in cliques]
                        clique_edges.append(cliques1)
                    if len(rows['entry2']) > 1:
                        cliques = [x for x in combinations(rows['entry2'], 2)]
                        cliques2 = [tup + ('type 2', 'undirectional', 'clique') for tup in cliques]
                        clique_edges.append(cliques2)
                clique2df = [e for edge in clique_edges for e in edge]
                cliquedf = pd.DataFrame.from_records(clique2df, columns = ['entry1', 'entry2', 'type', 'value', 'name'])
           
                edges = []
                for index, rows in df.iterrows():
                    lists = rows['entry1'] + rows['entry2']
                    # Cliques here inherit neighbor weights, but will be overwritten by above
                    cliques = [x for x in combinations(lists, 2)]
                    network = [tup + (rows['types'], rows['value'], rows['name'], rows['pos1'], rows['pos2']) for tup in cliques]
                    edges.append(network)
            
                # This removes edges which contain +p (phosphorylation) these oftentimes
                # overwrite important weight attributes while providing no vital information
                # edges2df = [e for edge in edges for e in edge if '+p' not in e and '-p' not in e]
            
                # Standard line for obtaining a dataframe of edges
                edges2df = [e for edge in edges for e in edge]
                # Create pandas DF from edges
                df_out = pd.DataFrame.from_records(edges2df, columns = ['entry1', 'entry2', 'type', 'value', 'name', 'pos1', 'pos2'])
                
                # Graphics
                if graphics:
                    pos_dict1 = {}
                    pos_dict2 = {}
                    for index, rows in df_out.iterrows():
                        pos_dict1[rows['entry1']] = rows['pos1']
                        pos_dict2[rows['entry2']] = rows['pos2']
                    pos = pos_dict1 | pos_dict2
                    json_dict = json.dumps(pos)
                    with open(output_path / '{}_graphics.txt'.format(pathway), 'w') as outfile:
                        outfile.write(json_dict)
                
                dft = df_out.groupby(['entry1', 'entry2'])['type'].apply(list).reset_index()
                dfv = df_out.groupby(['entry1', 'entry2'])['value'].apply(list).reset_index()
                dfn = df_out.groupby(['entry1', 'entry2'])['name'].apply(list).reset_index()
                dfx = dft
                dfx['value'] = dfv['value'].agg(','.join)
                dfx['name'] = dfn['name'].agg(','.join)
                dfx['type'] = dft['type'].agg(','.join)
                # Ensures independently parsed cliques overwrite the cliques, which inherited neighbor weights
                xdf = pd.concat([dfx, cliquedf]).drop_duplicates(subset = ['entry1', 'entry2'], keep = 'last')

                if xdf[(xdf['entry1'].str.startswith('cpd:')) | (xdf['entry2'].str.startswith('cpd:'))].empty == True and xdf[(xdf['entry1'].str.startswith('undefined')) | (xdf['entry2'].str.startswith('undefined'))].empty == True:
                    # If pathway has no compounds or undefined nodes, write file
                    # Note: since this isn't a mixed pathway, "path:" nodes are excluded
                    xdf_out = xdf[(~xdf['entry1'].str.startswith('path')) & (~xdf['entry2'].str.startswith('path'))]
                    xdf_out.to_csv(output_path / '{}.tsv'.format(pathway), sep = '\t', index = False)
                else:
                    # These next series of steps are for propagating compounds and undefined nodes
                    # Uses networkx
                    G = nx.from_pandas_edgelist(xdf, source = 'entry1', target = 'entry2', edge_attr = 'name', create_using = nx.DiGraph())
                    new_edges = []
                    for node in G.nodes:
                        # Gather roots and leaflets
                        roots = [n for n, d in G.in_degree() if d == 0]
                        leaflets = [n for n, d in G.out_degree() if d == 0]
                        # Find compounds or undefined proteins that might need propagation
                        if node.startswith('cpd') or node.startswith('undefined'):
                            if node in roots or node in leaflets:
                                # Passes root nodes and leaflet nodes
                                # These do not need propagation as they terminate
                                pass
                            else:
                                out_edges = [e for e in G.out_edges(node)]
                                in_edges = [e for e in G.in_edges(node)]
                                for i in in_edges:
                                    for o in out_edges:
                                        if not i[0].startswith('cpd') and not o[1].startswith('cpd') and not i[0].startswith('undefined') and not o[1].startswith('undefined') and not i[0].startswith('path') and not o[1].startswith('path'):
                                            # Simple compound propagation removes compound between two genes
                                            # Example: hsa:xxx -> cpd:xxx -> hsa:xxx to hsa:xxx -> hsa:xxx
                                            new_edges.append([i[0], o[1], 'CPp', 'Custom', 'compound propagation'])
                                        else:
                                            # Loops through roots and leaves to find the start and end of each node that is propagated
                                            # These pathways have copious amounts of compounds and undefined genes in between the propagated genes
                                            # This loop also picks up on non-proteins that are left out if the above simple compound propagation is used
                                            for root in roots:
                                                for leaf in leaflets:
                                                    if nx.has_path(G, root, node) == True and nx.has_path(G, node, leaf) == True:
                                                        # Uses the shortest path between the root/leaf and query node
                                                        rpath = [p for p in nx.shortest_path(G, root, node)]
                                                        lpath = [p for p in nx.shortest_path(G, node, leaf)]
                                                        # Skip paths that have no proteins
                                                        if all(node.startswith('cpd') or node.startswith('undefined') or node.startswith('path') for node in rpath) == True or all(node.startswith('cpd') or node.startswith('undefined') or node.startswith('path') for node in lpath) == True:
                                                            pass
                                                        else:
                                                            # Indexes all elements in the shortest path list that is a gene
                                                            rindex = [index for index, element in enumerate(rpath) if not element.startswith('cpd') and not element.startswith('undefined') and not element.startswith('path')]
                                                            lindex = [index for index, element in enumerate(lpath) if not element.startswith('cpd') and not element.startswith('undefined') and not element.startswith('path')]
                                                            # Here we use the maximum of the root path and the minimum of the leaf path to successfully propagate compounds
                                                            # Note below example
                                                            # [mmu:x, cpd:###, cpd:x] --> max is mmu:x 
                                                            # [cpd:x, cpd:###, undefined, mmu:y, mmu:###] --> min is mmu:y
                                                            # creates edge [mmu:x, mmu:y]
                                                            new_edges.append([rpath[max(rindex)], lpath[min(lindex)], 'CPp', 'Custom', 'compound propagation'])
                    # Creates a dataframe of the new edges that are a result of compound propagation
                    new_edges_df = pd.DataFrame(new_edges, columns = df_out.drop(['pos1', 'pos2'], axis = 1).columns)
                    # Concatenates the new edges with the edges from the above (cliques and original parsed edges)
                    df0 = pd.concat([xdf, new_edges_df])
                    # Drop any duplicated edges
                    df1 = df0.drop_duplicates()
                    # Removes compounds and undefined as they were propagated and no longer needed
                    df2 = df1[(~df1['entry1'].str.startswith('cpd')) & (~df1['entry2'].str.startswith('cpd')) & (~df1['entry1'].str.startswith('undefined')) & (~df1['entry2'].str.startswith('undefined')) & (~df1['entry1'].str.startswith('path')) & (~df1['entry2'].str.startswith('path'))]
                    df2.to_csv(output_path / '{}.tsv'.format(pathway), sep = '\t', index = False)
        else:
            output_path = wd / 'kegg_gene_network_{}'.format(species)
            output_path.mkdir(exist_ok = True)
            
            typer.echo(f'Now parsing: {title}...')
           
            e1 = []
            e2 = []
            n = []
            v = []
            for relation in root.findall('relation'):
                e1.append(relation.get('entry1'))
                e2.append(relation.get('entry2'))
                for subtype in relation.findall('subtype'):
                    n.append(subtype.get('name'))
                    v.append(subtype.get('value'))
           
            d = []
            for relation in root.findall('relation'):
                for subtype in relation:
                    d1=relation.attrib
                    d2=subtype.attrib
                    d3=json.dumps(d1),json.dumps(d2)
                    d.append(d3)    

            edgelist=[]
            # Takes json dictionary and removes formatting in order to obtain an edgelist
            # This odd line of code is necessary  because of the various nested and non-nested subtypes
            # This allows for edges to inherit weights from a nested subtype
            for line in d:
                x=line[0].replace("{","").replace("}","").replace('"entry1":',"")\
                .replace('"entry2":',"").replace('"type":',"").replace('"name":',"")\
                .replace('"value":',"").replace('"','').replace(',',"\t").replace(' ', '')
                y=line[1].replace("{","").replace("}","").replace('"name":',"")\
                .replace('"',"").replace('value:',"").replace(",",'\t').replace(' ', '')
                edgelist.append(x+"\t"+y)

            df=pd.DataFrame(edgelist)
       
            if df.empty:
                typer.echo(f'File "{file}" cannot be parsed.\nVisit {pathway_link} for pathway details.\nThere are likely no edges in which to parse...')
            else:
                df=df[0].str.split("\t", expand=True).rename({0: 'entry1',1: 'entry2',
                                                      2: 'types', 3:'name',
                                                      4: 'value'}, axis='columns')

                entry_dict = defaultdict(list)
                for entries in root.findall('entry'):
                    for key, items in entries.attrib.items():
                        entry_dict[key].append(items)
           
                entry_id=[]
                entry_name=[]
                entry_type=[]
                for key, items in entry_dict.items():
                    if key == 'id':
                        for i in items:
                            entry_id.append(i)
                    if key == 'name':
                        for i in items:
                            entry_name.append(i)
                    if key == 'type':
                        for i in items:
                            entry_type.append(i)
                
                if unique:
                    conversion_dictionary = conv_dict_unique(root)
                else:
                    conversion_dictionary = conv_dict(root)
           
                df['entry1'] = df['entry1'].map(conversion_dictionary)
                df['entry2'] = df['entry2'].map(conversion_dictionary)
                df['entry1'] = df['entry1'].astype(str).str.split(' ', expand = False)
                df['entry2'] = df['entry2'].astype(str).str.split(' ', expand = False)
           
                # Parse the cliques seperate so they won't inherit neighbor weights
                # Allows for custom weights so user knows which are customly parsed
                clique_edges = []
                for index, rows in df.iterrows():
                    if len(rows['entry1']) > 1:
                        cliques = [x for x in combinations(rows['entry1'], 2)]
                        cliques1 = [tup + ('type 2', 'undirectional', 'clique') for tup in cliques]
                        clique_edges.append(cliques1)
                    if len(rows['entry2']) > 1:
                        cliques = [x for x in combinations(rows['entry2'], 2)]
                        cliques2 = [tup + ('type 2', 'undirectional', 'clique') for tup in cliques]
                        clique_edges.append(cliques2)
                clique2df = [e for edge in clique_edges for e in edge]
                cliquedf = pd.DataFrame.from_records(clique2df, columns = ['entry1', 'entry2', 'type', 'value', 'name'])
           
                edges = []
                for index, rows in df.iterrows():
                    lists = rows['entry1'] + rows['entry2']
                    # Cliques here inherit neighbor weights, but will be overwritten by above
                    cliques = [x for x in combinations(lists, 2)]
                    network = [tup + (rows['types'], rows['value'], rows['name']) for tup in cliques]
                    edges.append(network)
            
                # This removes edges which contain +p (phosphorylation) these oftentimes
                # overwrite important weight attributes while providing no vital information
                # edges2df = [e for edge in edges for e in edge if '+p' not in e and '-p' not in e]
            
                # Standard line for obtaining a dataframe of edges
                edges2df = [e for edge in edges for e in edge]
                # Create pandas DF from edges
                df_out = pd.DataFrame.from_records(edges2df, columns = ['entry1', 'entry2', 'type', 'value', 'name'])
                
                dft = df_out.groupby(['entry1', 'entry2'])['type'].apply(list).reset_index()
                dfv = df_out.groupby(['entry1', 'entry2'])['value'].apply(list).reset_index()
                dfn = df_out.groupby(['entry1', 'entry2'])['name'].apply(list).reset_index()
                dfx = dft
                dfx['value'] = dfv['value'].agg(','.join)
                dfx['name'] = dfn['name'].agg(','.join)
                dfx['type'] = dft['type'].agg(','.join)
                # Ensures independently parsed cliques overwrite the cliques, which inherited neighbor weights
                xdf = pd.concat([dfx, cliquedf]).drop_duplicates(subset = ['entry1', 'entry2'], keep = 'last')

                if xdf[(xdf['entry1'].str.startswith('cpd:')) | (xdf['entry2'].str.startswith('cpd:'))].empty == True and xdf[(xdf['entry1'].str.startswith('undefined')) | (xdf['entry2'].str.startswith('undefined'))].empty == True:
                    # If pathway has no compounds or undefined nodes, write file
                    # Note: since this isn't a mixed pathway, "path:" nodes are excluded
                    xdf_out = xdf[(~xdf['entry1'].str.startswith('path')) & (~xdf['entry2'].str.startswith('path'))]
                    xdf_out.to_csv(output_path / '{}.tsv'.format(pathway), sep = '\t', index = False)
                else:
                    # These next series of steps are for propagating compounds and undefined nodes
                    # Uses networkx
                    G = nx.from_pandas_edgelist(xdf, source = 'entry1', target = 'entry2', edge_attr = 'name', create_using = nx.DiGraph())
                    new_edges = []
                    for node in G.nodes:
                        # Gather roots and leaflets
                        roots = [n for n, d in G.in_degree() if d == 0]
                        leaflets = [n for n, d in G.out_degree() if d == 0]
                        # Find compounds or undefined proteins that might need propagation
                        if node.startswith('cpd') or node.startswith('undefined'):
                            if node in roots or node in leaflets:
                                # Passes root nodes and leaflet nodes
                                # These do not need propagation as they terminate
                                pass
                            else:
                                out_edges = [e for e in G.out_edges(node)]
                                in_edges = [e for e in G.in_edges(node)]
                                for i in in_edges:
                                    for o in out_edges:
                                        if not i[0].startswith('cpd') and not o[1].startswith('cpd') and not i[0].startswith('undefined') and not o[1].startswith('undefined') and not i[0].startswith('path') and not o[1].startswith('path'):
                                            # Simple compound propagation removes compound between two genes
                                            # Example: hsa:xxx -> cpd:xxx -> hsa:xxx to hsa:xxx -> hsa:xxx
                                            new_edges.append([i[0], o[1], 'CPp', 'Custom', 'compound propagation'])
                                        else:
                                            # Loops through roots and leaves to find the start and end of each node that is propagated
                                            # These pathways have copious amounts of compounds and undefined genes in between the propagated genes
                                            # This loop also picks up on non-proteins that are left out if the above simple compound propagation is used
                                            for root in roots:
                                                for leaf in leaflets:
                                                    if nx.has_path(G, root, node) == True and nx.has_path(G, node, leaf) == True:
                                                        # Uses the shortest path between the root/leaf and query node
                                                        rpath = [p for p in nx.shortest_path(G, root, node)]
                                                        lpath = [p for p in nx.shortest_path(G, node, leaf)]
                                                        # Skip paths that have no proteins
                                                        if all(node.startswith('cpd') or node.startswith('undefined') or node.startswith('path') for node in rpath) == True or all(node.startswith('cpd') or node.startswith('undefined') or node.startswith('path') for node in lpath) == True:
                                                            pass
                                                        else:
                                                            # Indexes all elements in the shortest path list that is a gene
                                                            rindex = [index for index, element in enumerate(rpath) if not element.startswith('cpd') and not element.startswith('undefined') and not element.startswith('path')]
                                                            lindex = [index for index, element in enumerate(lpath) if not element.startswith('cpd') and not element.startswith('undefined') and not element.startswith('path')]
                                                            # Here we use the maximum of the root path and the minimum of the leaf path to successfully propagate compounds
                                                            # Note below example
                                                            # [mmu:x, cpd:###, cpd:x] --> max is mmu:x 
                                                            # [cpd:x, cpd:###, undefined, mmu:y, mmu:###] --> min is mmu:y
                                                            # creates edge [mmu:x, mmu:y]
                                                            new_edges.append([rpath[max(rindex)], lpath[min(lindex)], 'CPp', 'Custom', 'compound propagation'])
                    # Creates a dataframe of the new edges that are a result of compound propagation
                    new_edges_df = pd.DataFrame(new_edges, columns = df_out.drop(['pos1', 'pos2'], axis = 1).columns)
                    # Concatenates the new edges with the edges from the above (cliques and original parsed edges)
                    df0 = pd.concat([xdf, new_edges_df])
                    # Drop any duplicated edges
                    df1 = df0.drop_duplicates()
                    # Removes compounds and undefined as they were propagated and no longer needed
                    df2 = df1[(~df1['entry1'].str.startswith('cpd')) & (~df1['entry2'].str.startswith('cpd')) & (~df1['entry1'].str.startswith('undefined')) & (~df1['entry2'].str.startswith('undefined')) & (~df1['entry1'].str.startswith('path')) & (~df1['entry2'].str.startswith('path'))]
                    df2.to_csv(output_path / '{}.tsv'.format(pathway), sep = '\t', index = False)


        
if __name__ == '__main__':
    app()
