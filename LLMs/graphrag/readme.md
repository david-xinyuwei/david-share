
# Graphrag configure and validation
**Notice:**
graphrag is a Microsoft opensource project, link:
***https://github.com/microsoft/graphrag.git***


## Result show
The final graph generated during the test is under ***results*** directory：
- knowledge_graph.html is a graph that is dynamic in itself 
- knowledge_graph1.html is a static graph.

Both graphs have the same data source.

![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/1.png)

## How to fast install
graphrag is an open source project created not long ago, in the installation process will inevitably encounter some problems is normal. If you are just starting out with this project , it is recommended to use its sub-projects, you could follow it to do One-click deployment on Azure saves a lot of time.
https://github.com/Azure-Samples/graphrag-accelerator

The architecture diagram is shown below:
![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/2.png)


####  Step1: follow this guide to install env on Azure.
Deploy guide:
***https://github.com/Azure-Samples/graphrag-accelerator/blob/main/docs/DEPLOYMENT-GUIDE.md***

When onfigure deploy parameters, refer to following:
```
(base) root@davidwei:~/graphrag-accelerator/infra# cat deploy.parameters.json
{
  "GRAPHRAG_API_BASE": "https://****.openai.azure.com/",
  "GRAPHRAG_API_VERSION": "2024-02-15-preview",
  "GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME": "text-embedding-ada-002",
  "GRAPHRAG_EMBEDDING_MODEL": "text-embedding-ada-002",
  "GRAPHRAG_LLM_DEPLOYMENT_NAME": "4turbo-2024-04-09",
  "GRAPHRAG_LLM_MODEL": "gpt-4",
  "LOCATION": "eastus2",
  "RESOURCE_GROUP": "davidAI"
```

Installation will take ~40-50 minutes to deploy.Don't worry that the installation didn't work all at once, when the install command is initiated again, the script will first check for already installed components and then continue with the installation.


####  Step2: Get the URL and key to APIM as an API for Graphrag.
![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/3.png)

![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/4.png)

####  Step3: run test
Refer to following link to create a dataset:

*** https://github.com/Azure-Samples/graphrag-accelerator/tree/main/notebooks ***

Then run ipynb file 

## Ipynb file Results analyze

### In 1-Quickstart.ipynb
In this ipynb file, apart from the basic configuration, the main comparison is made by global and local search.

![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/5.png)

![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/6.png)

In response to an identical question:
prompt："Who are the primary actors in Alaska and California communities?"  

Global query result：
```
### Primary Actors in Alaska

#### Government and Legislative Influence
In Alaska, the Alaska State Legislature holds significant responsibilities, managing both legislative and judicial duties. This body plays a crucial role in overseeing the distribution of dividends from the Permanent Fund's growth to eligible Alaskans, directly impacting the financial well-being of the residents [Data: Reports (135, 133)].

#### Educational and Cultural Institutions
The University of Alaska system is a key educational actor, with initiatives like the Alaska Scholars Program aimed at retaining high-achieving students within the state [Data: Reports (107, 54)]. Cultural influences include the Russian Orthodox Church, which plays a central role in the cultural communities of Alaska [Data: Reports (61)].

#### Environmental and Land Management
Environmental management and land use are significantly influenced by entities such as the Arctic National Wildlife Refuge, Pebble Mine, and various U.S. federal agencies including the United States Fish and Wildlife Service and the Bureau of Land Management [Data: Reports (55)].

#### Transportation and Infrastructure
Alaska Airlines and the Essential Air Service Program are crucial for providing air connectivity, especially to remote areas and regional hubs, facilitating both local and external mobility [Data: Reports (98)].

#### Indigenous and Cultural Representation
The Tsimshian people and the settlement on Annette Island represent key cultural and historical actors, embodying the interests of indigenous communities in Alaska [Data: Reports (114)].

### Primary Actors in California

#### Political and Legislative Dominance
The Democratic Party holds a supermajority in the California state legislature, significantly shaping state policies and governance. Governor Gavin Newsom also plays a pivotal role in representing the state government and influencing policies [Data: Reports (130)].

#### Judicial and Legal Framework
The State Judiciary, the Judicial Council, and the State Bar of California are significant actors in governing California's judiciary system, affecting legal outcomes and practices across the state [Data: Reports (136, 134)].

#### Energy Infrastructure
Entities like PATH 46 and natural gas-fired power plants are crucial for energy transmission and form a vital part of the state's energy infrastructure, influencing both economic and environmental aspects [Data: Reports (29)].

#### Media and Economic Influence
Major American Television Commercial Broadcast Networks impact the media landscape, while the Congressional Research Service plays a role in shaping economic policies [Data: Reports (117, 127)].

#### Cultural and Social Movements
The proponents of the English-Only Movement and California Proposition 63 have significantly shaped language policies and social dynamics within the state [Data: Reports (34)].

These actors collectively contribute to the unique political, environmental, cultural, and economic landscapes of Alaska and California, each playing specialized roles that influence various aspects of life in these states.

### Primary Actors in California

California's landscape of primary actors is diverse, spanning economic, technological, educational, and entertainment sectors. The State of California, Silicon Valley, and the University of California system are pivotal in driving the state's economy and technological and educational advancements [Data: Reports (42, 41, 30)]. Caltrans manages state transportation, while the Judicial Council oversees judiciary administration [Data: Reports (8, 26)]. The entertainment industry is significantly influenced by Hollywood and the 'Big Five' film studios [Data: Reports (12)]. Historical contributions are noted with Father-President Serra's establishment of Spanish missions, which influenced the development of major cities [Data: Reports (22)]. The California Community Colleges System and the California State University system are key in providing educational services and pathways for higher education [Data: Reports (13)].

These actors collectively contribute to the robust functionality and development of their respective states, addressing various sectoral needs and enhancing regional connectivity and growth.

```
Local query result：
```
# Analysis of Primary Actors in Alaska and California Communities

## Alaska

### Indigenous Communities
Indigenous peoples, including Alaska Natives, are pivotal actors in Alaska. They are deeply engaged in local politics and manage significant tracts of land through Native corporations [Data: Entities (535); Relationships (803)].

### Political Entities
Alaskan politicians and the Alaska Statehood Committee have historically played significant roles in shaping state policies and advocating for state investments [Data: Entities (339, 100); Relationships (862, 698)].

### Economic Contributors
Employment sectors such as government, natural resource extraction, and tourism are major players in Alaska's economy. Military bases also contribute significantly to employment in certain boroughs [Data: Entities (306); Relationships (854, 855)].

### Cultural and Social Organizations
Organizations like the Anchorage Opera and various native corporations contribute to the cultural and social fabric of the state [Data: Entities (402); Relationships (593)].

## California

### Indigenous Peoples
Indigenous groups in California have a tragic history of displacement and violence but remain integral to the state's historical narrative [Data: Entities (30); Sources (181)].

### Religious Organizations
Major religious denominations such as the Southern Baptist Convention and The Church of Jesus Christ of Latter-day Saints, along with diverse minority religious communities like Buddhists and Hindus, play significant roles in community dynamics and policies in California [Data: Entities (270, 269, 297, 293); Relationships (421, 420, 417, 416)].

### Demographic and Policy Influencers
Organizations like the American Community Survey and HUD's Annual Homeless Assessment Report provide critical data influencing public policy and community planning in California [Data: Entities (240, 239); Relationships (373, 362)].

### Economic and Social Impact Groups
Entities involved in addressing homelessness and demographic shifts, such as HUD, are crucial in developing interventions to improve life quality for vulnerable populations in California [Data: Entities (239); Relationships (362)].

## Conclusion
Both Alaska and California feature a diverse array of primary actors ranging from indigenous communities and political entities to economic sectors and cultural organizations. These actors play crucial roles in shaping the social, economic, and political landscapes of their respective states.
```

#### Compare result between first segment(global query）  and second segment(local query) 
Upon comparing the two segments provided, it is evident that both offer a comprehensive analysis of the primary actors in Alaska and California, but they differ in structure and detail:
##### Structure and Focus:
- The first segment is organized by categories such as government, education, environmental management, and cultural representation for each state. It provides a broad overview of the key actors and their roles within these categories.
- The second segment is structured around community-specific actors and their impacts, focusing more on the interactions and relationships between different entities and groups within Alaska and California.

##### Detail and Data Reference:
- The first segment includes specific references to data reports, which adds credibility and a basis for the claims made about the roles of various actors. Each actor's influence is backed by numbered reports, providing a clear trail for verification.
- The second segment also references data entities and relationships but uses a different notation (e.g., Entities (535); Relationships (803)). This approach highlights the interconnectedness of the actors and their roles but might be less straightforward for readers unfamiliar with this notation.

##### Content Coverage:
- The first segment covers a wide range of sectors and their key actors, from political bodies to cultural institutions and environmental management. It provides a holistic view of the influential forces in each state.
- The second segment delves deeper into the societal impacts and historical contexts, particularly emphasizing the roles of indigenous communities and economic contributors in Alaska, and demographic influencers and social impact groups in California. This segment offers a more in-depth look at the social dynamics and historical influences.

##### Analytical Depth:
- The first segment is more descriptive, listing key actors and their roles without much analysis of how these roles interact or the broader implications.
- The second segment provides more analysis on how these actors influence and shape the states' policies, economies, and social structures, giving a more dynamic and interconnected view of the states' landscapes.

#### Summary
The first segment is useful for obtaining a clear and structured overview of the primary actors in Alaska and California, while the second segment offers a more nuanced and interconnected analysis, focusing on the impacts and relationships among the actors. Both segments are informative, but the choice between them would depend on whether the reader prefers a straightforward listing or a deeper analytical perspective.



## 2-Advanced_Getting_Started.ipynb
![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/7.png)

In this ipynb, in addition to performing the comparison between global query and local query, the API was called to generate Graphrag knowledge.

![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/8.png)



















































