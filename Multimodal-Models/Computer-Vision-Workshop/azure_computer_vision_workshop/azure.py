#
# Python functions for visual search with Azure Computer Vision 4 Florence
#
# File: azure.py
#
# Azure Service : Azure Computer Vision 4.0 (Florence)
# Usecase: Visual search using image or text to find similar images
# Python version: 3.8.5
#
# Date: 3 May 2023
# Author: Serge Retkowsky | Microsoft | https://github.com/retkowsky
#

import datetime
import json
import math
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import os
import pandas as pd
import requests
import seaborn as sns

from dotenv import load_dotenv
from io import BytesIO
from PIL import Image


# Reading Azure Computer Vision 4 endpoint and key from the env file

load_dotenv("azure.env")
key = os.getenv("azure_cv_key")
endpoint = os.getenv("azure_cv_endpoint")


# Python functions

def image_embedding(image_file):
    """
    Embedding image using Azure Computer Vision 4 Florence
    """
    version = "?api-version=2023-02-01-preview&modelVersion=latest"
    vec_img_url = endpoint + "/computervision/retrieval:vectorizeImage" + version

    headers_image = {
        'Content-type': 'application/octet-stream',
        'Ocp-Apim-Subscription-Key': key
    }

    with open(image_file, 'rb') as f:
        data = f.read()
    r = requests.post(vec_img_url, data=data, headers=headers_image)
    image_emb = r.json()['vector']

    return image_emb


def image_embedding_batch(image_file):
    """
    Embedding image using Azure Computer Vision 4 Florence
    """
    version = "?api-version=2023-02-01-preview&modelVersion=latest"
    vec_img_url = endpoint + "/computervision/retrieval:vectorizeImage" + version

    headers_image = {
        'Content-type': 'application/octet-stream',
        'Ocp-Apim-Subscription-Key': key
    }

    with open(image_file, 'rb') as f:
        data = f.read()
    r = requests.post(vec_img_url, data=data, headers=headers_image)
    image_emb = r.json()['vector']

    return image_emb, r


def text_embedding(promptxt):
    """
    Embedding text using Azure Computer Vision 4 Florence
    """
    version = "?api-version=2023-02-01-preview&modelVersion=latest"
    vec_txt_url = endpoint + "/computervision/retrieval:vectorizeText" + version

    headers_prompt = {
        'Content-type': 'application/json',
        'Ocp-Apim-Subscription-Key': key
    }

    prompt = {'text': promptxt}
    r = requests.post(vec_txt_url,
                      data=json.dumps(prompt),
                      headers=headers_prompt)
    text_emb = r.json()['vector']

    return text_emb


def get_cosine_similarity(vector1, vector2):
    """
    Get cosine similarity value between two embedded vectors
    Using sklearn
    """
    dot_product = 0
    length = min(len(vector1), len(vector2))

    for i in range(length):
        dot_product += vector1[i] * vector2[i]

    cosine_similarity = dot_product / (math.sqrt(sum(x * x for x in vector1))\
                                       * math.sqrt(sum(x * x for x in vector2)))

    return cosine_similarity


def view_image(image_file):
    """
    View image file
    """
    plt.imshow(Image.open(image_file))
    plt.axis('off')
    plt.title("Image: " + image_file, fontdict={'fontsize': 10})
    plt.show()


def get_similar_images_using_image(list_emb, image_files, image_file):
    """
    Get similar images using an image with Azure Computer Vision 4 Florence
    """
    ref_emb = image_embedding(image_file)
    idx = 0
    results_list = []

    for emb_image in list_emb:
        simil = get_cosine_similarity(ref_emb, list_emb[idx])
        results_list.append(simil)
        idx += 1

    df_files = pd.DataFrame(image_files, columns=['image_file'])
    df_simil = pd.DataFrame(results_list, columns=['similarity'])
    df = pd.concat([df_files, df_simil], axis=1)
    df.sort_values('similarity',
                   axis=0,
                   ascending=False,
                   inplace=True,
                   na_position='last')

    return df


def get_similar_images_using_prompt(prompt, image_files, list_emb):
    """
    Get similar umages using a prompt with Azure Computer Vision 4 Florence
    """
    prompt_emb = text_embedding(prompt)
    idx = 0
    results_list = []

    for emb_image in list_emb:
        simil = get_cosine_similarity(prompt_emb, list_emb[idx])
        results_list.append(simil)
        idx += 1

    df_files = pd.DataFrame(image_files, columns=['image_file'])
    df_simil = pd.DataFrame(results_list, columns=['similarity'])
    df = pd.concat([df_files, df_simil], axis=1)
    df.sort_values('similarity',
                   axis=0,
                   ascending=False,
                   inplace=True,
                   na_position='last')

    return df


def get_topn_images(df, topn=5, disp=False):
    """
    Get topn similar images
    """
    idx = 0
    if disp:
        print("\033[1;31;34mTop", topn, "images:\n")

    topn_list = []
    simil_topn_list = []

    while idx < topn:
        row = df.iloc[idx]
        if disp:
            print(
                f"{idx+1:03} {row['image_file']} with similarity index = {row['similarity']}"
            )
        topn_list.append(row['image_file'])
        simil_topn_list.append(row['similarity'])
        idx += 1

    return topn_list, simil_topn_list


def view_similar_images_using_image(reference_image, topn_list, 
                                    simil_topn_list, num_rows=2, num_cols=3):
    """
    Plot similar images using an image with Azure Computer Vision 4 Florence
    """
    img_list = topn_list
    if img_list[0] != reference_image:
        img_list.insert(0, reference_image)

    num_images = len(img_list)
    FIGSIZE = (12, 8)
    fig, axes = plt.subplots(nrows=num_rows, ncols=num_cols, figsize=FIGSIZE)

    size = 8 if num_rows >= 3 else 10

    for i, ax in enumerate(axes.flat):
        if i < num_images:
            img = mpimg.imread(img_list[i])
            ax.imshow(img)

            if i == 0:
                imgtitle = f"Image to search:\n {os.path.basename(img_list[i])}"
                ax.set_title(imgtitle, size=size, color='blue')
            else:
                imgtitle = f"Top {i}: {os.path.basename(img_list[i])}\nSimilarity = {round(simil_topn_list[i-1], 5)}"
                ax.set_title(imgtitle, size=size, color='green')
            ax.axis('off')

        else:
            ax.axis('off')

    plt.show()
    
    print("\033[1;31;32m",
          datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          "Powered by Azure Computer Vision Florence")


def view_similar_images_using_prompt(query, topn_list, simil_topn_list,
                                     num_rows=2, num_cols=3):
    """
    Plot similar images using a prompt with Azure Computer Vision 4 Florence
    """
    print("\033[1;31;34m")
    print("Similar images using query =", query)
    
    num_images = len(topn_list)
    FIGSIZE = (12, 8)
    fig, axes = plt.subplots(nrows=num_rows, ncols=num_cols, figsize=FIGSIZE)

    size = 8 if num_rows >= 3 else 10

    for i, ax in enumerate(axes.flat):
        if i < num_images:
            img = mpimg.imread(topn_list[i])
            ax.imshow(img)
            imgtitle = f"Top {i+1}: {os.path.basename(topn_list[i])}\nSimilarity = {round(simil_topn_list[i], 5)}"
            ax.set_title(imgtitle, size=size, color='green')
            ax.axis('off')

        else:
            ax.axis('off')

    plt.show()
    
    print("\033[1;31;32m",
          datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          "Powered by Azure Computer Vision Florence")


def get_img_embedding_multiprocessing(image_file):
    """
    Compute embeddings with Azure Computer Vision 4 Florence using multiprocessing
    """
    version = "?api-version=2023-02-01-preview&modelVersion=latest"
    vec_img_url = endpoint + "/computervision/retrieval:vectorizeImage" + version

    headers_images = {
        'Content-type': 'application/octet-stream',
        'Ocp-Apim-Subscription-Key': key
    }

    emb = requests.post(vec_img_url,
                        data=open(image_file, 'rb').read(),
                        headers=headers_images).json()['vector']
    return emb


def remove_background(image_file):
    """
    Removing background from an image file using Azure Computer Vision 4
    """
    remove_background_url = endpoint +\
    "/computervision/imageanalysis:segment?api-version=2023-02-01-preview&mode=backgroundRemoval"

    headers_background = {
        'Content-type': 'application/octet-stream',
        'Ocp-Apim-Subscription-Key': key
    }

    print(
        "Removing background from the image using Azure Computer Vision 4.0..."
    )

    with open(image_file, 'rb') as f:
        data = f.read()

    r = requests.post(remove_background_url, data=data, headers=headers_background)

    output_image = "without_background.jpg"
    with open(output_image, 'wb') as f:
        f.write(r.content)
    print("Done")

    return output_image


def side_by_side_images(image_file1, image_file2):
    """
    Display two images side by side
    """
    fig, ax = plt.subplots(1, 2, figsize=(10, 5))
    ax[0].imshow(plt.imread(image_file1))
    ax[1].imshow(plt.imread(image_file2))
    
    for i in range(2):
        ax[i].axis('off')
        ax[i].set_title(['Initial image', 'Without the background'][i])
    fig.suptitle('Background removal with Azure Computer Vision 4', fontsize=11)
    plt.tight_layout()
    plt.show()


def describe_image_with_AzureCV4(image_file):
    """
    Get tags & caption from an image using Azure Computer Vision 4 Florence
    """
    options = "&features=tags,caption"
    model = "?api-version=2023-02-01-preview&modelVersion=latest"
    url = endpoint + "/computervision/imageanalysis:analyze" + model + options

    headers_cv = {
        'Content-type': 'application/octet-stream',
        'Ocp-Apim-Subscription-Key': key
    }

    with open(image_file, 'rb') as f:
        data = f.read()

    r = requests.post(url, data=data, headers=headers_cv)
    results = r.json()

    print("Automatic analysis of the image using Azure Computer Vision 4.0:")
    print("\033[1;31;34m")
    print("   Main caption:")
    print(
        f"    {results['captionResult']['text']} = {results['captionResult']['confidence']:.3f}"
    )

    print("\033[1;31;32m")
    print("   Detected tags:")
    for tag in results['tagsResult']['values']:
        print(f"    {tag['name']:18} = {tag['confidence']:.3f}")


def get_image_from_url(image_url):
    """
    Get an image from an url, download and save the image
    """
    response = requests.get(image_url)
    image = Image.open(BytesIO(response.content)).convert("RGB")
   
    output_image = 'download.jpg'
    image.save(output_image)
    
    return image


def get_results_using_image(reference_image, nobackground_image,
                            image_files, list_emb, topn, disp=False):
    """
    Get the topn results from a visual search using an image
    Will generate a df, display the topn images and return the df
    """
    df = get_similar_images_using_image(list_emb, image_files, nobackground_image)
    df.head(topn).style.background_gradient(
        cmap=sns.light_palette("green", as_cmap=True))
  
    topn_list, simil_topn_list = get_topn_images(df, topn, disp=disp)
    nb_cols = 3
    nb_rows = (topn + nb_cols - 1) // nb_cols
    view_similar_images_using_image(reference_image, topn_list, simil_topn_list, 
                                    num_cols=nb_cols, num_rows=nb_rows)

    return df


def get_results_using_prompt(query, image_files, list_emb, topn, disp=False):
    """
    Get the topn results from a visual search using a text query
    Will generate a df, display the topn images and return the df
    """
    df = get_similar_images_using_prompt(query, image_files, list_emb)
    df.head(topn).style.background_gradient(
        cmap=sns.light_palette("green", as_cmap=True))
  
    topn_list, simil_topn_list = get_topn_images(df, topn, disp=disp)
    nb_cols = 3
    nb_rows = (topn + nb_cols - 1) // nb_cols
    view_similar_images_using_prompt(query, topn_list, simil_topn_list, 
                                    num_cols=nb_cols, num_rows=nb_rows)

    return df




