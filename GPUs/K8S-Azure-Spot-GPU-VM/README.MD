最新发现一个很不错的开源工具，可以帮助我们降低深度学习推理的成本。

Karpenter是一个用于Kubernetes集群的节点自动配置工具，它通过AKS Karpenter Provider在AKS集群上启用节点自动配置功能 。Karpenter的主要功能包括监控Kubernetes调度器标记为不可调度的Pods，评估Pods请求的调度约束（资源请求、节点选择器、亲和性、容忍性和拓扑扩散约束），根据这些约束配置满足要求的节点，并在这些节点不再需要时移除它们。此外，Karpenter还能够将现有节点整合到更便宜、利用率更高的节点上 。

使用场景方面，Karpenter适用于需要动态调整Kubernetes集群资源配置的场景，特别是在工作负载变化较大、需要频繁调整节点配置以适应不同工作负载需求的环境中。例如，对于需要根据实际使用情况自动扩展或缩减节点数量的应用，Karpenter可以自动化这一过程，提高资源配置的灵活性和效率 。

总的来说，Karpenter是一个强大的工具，能够帮助用户更高效、更经济地管理Kubernetes集群的资源配置。

在AKS的深度学习推理中，我们可以用SpotVM当成AKS的worker节点。

我们知道Azure SpotVM的成本相对正常的SKU低很多，但有被驱逐的风险。有了Karpenter后，我们有两种方案。

1.把多个SpotVM作为AKS的worker node，然后针对GPU推理的K8S SVC在多个worker node上创建多个副本，那么即使一个worker node被驱逐，业务也不受影响；如果能承受短时可能的短暂的业务中断，一个pod也可以，Karpenter发现worker节点被驱逐，能将pod在其他节点重启。多pod副本需要使用SVC和K8S的ingress。



2.创建多个Node pool，其中一个node pool使用spotvm，另外一个nodepool可以使用正常的GPU VM。然后针对不同的nodepool设置不同的weight。这样GPU pod的deployment就会先选择weight高的pool进行部署。

参照如下链接部署好一个支持Karpenter的AKS。

https://learn.microsoft.com/en-us/azure/aks/node-autoprovision?tabs=azure-cli

然后创建一个GPU pod的deployment，初始副本数设置为1：

xinyu [ ~ ]$ kubectl get deployment

```
NAME          READY   UP-TO-DATE   AVAILABLE   AGEsamples-gpu   0/1     1            0           2m24s
```

此时Azure开始创建spot gpu vm，如下所示：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWw11jbpOdXbHQj9TicjDGCm9yB5sp9WBZKFHH3ib7DDOsQsaibDFUU2WA7jExbpNsicvV8fNaXLOVhOA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

xinyu [ ~ ]$ kubectl get nodeclaims.karpenter.sh

```
NAME             TYPE                       ZONE              NODE   READY   AGEgpu-spot-57p8w   Standard_NC24ads_A100_v4   southeastasia-2          False   2m18s
```



xinyu [ ~ ]$ kubectl describe deployment samples-gpu

```
Name:                   samples-gpuNamespace:              defaultCreationTimestamp:      Sun, 24 Mar 2024 02:06:56 +0000Labels:                 app=samples-tf-mnist-demoAnnotations:            deployment.kubernetes.io/revision: 1Selector:               app=samples-tf-mnist-demoReplicas:               1 desired | 1 updated | 1 total | 0 available | 1 unavailableStrategyType:           RollingUpdateMinReadySeconds:        0RollingUpdateStrategy:  25% max unavailable, 25% max surgePod Template:Labels:  app=samples-tf-mnist-demoContainers:samples-tf-mnist-demo:Image:      mcr.microsoft.com/azuredocs/samples-tf-mnist-demo:gpuPort:       <none>Host Port:  <none>Args:--max_steps50000Limits:nvidia.com/gpu:  1Environment:       <none>Mounts:            <none>Volumes:             <none>Conditions:Type           Status  Reason----           ------  ------Available      False   MinimumReplicasUnavailableProgressing    True    ReplicaSetUpdatedOldReplicaSets:  <none>NewReplicaSet:   samples-gpu-95b9c58b6 (1/1 replicas created)Events:Type    Reason             Age    From                   Message----    ------             ----   ----                   -------Normal  ScalingReplicaSet  2m42s  deployment-controller  Scaled up replica set samples-gpu-95b9c58b6 to 1
```

大约2-3分钟，查看AKS节点，已经多个一个GPU VM。

xinyu [ ~ ]$ kubectl get nodes

```
NAME                                STATUS   ROLES   AGE   VERSIONaks-gpu-spot-57p8w                  Ready    agent   33s   v1.27.9aks-nodepool1-34768744-vmss000000   Ready    agent   54m   v1.27.9aks-nodepool1-34768744-vmss000001   Ready    agent   54m   v1.27.9aks-nodepool1-34768744-vmss000002   Ready    agent   54m   v1.27.9
```



xinyu [ ~ ]$ kubectl get pods

```
NAME                          READY   STATUS    RESTARTS   AGEsamples-gpu-95b9c58b6-nbg8g   1/1     Running   0          4m10s
```

登录pod，查看其中的GPU资源：

xinyu [ ~ ]$ kubectl exec -ti samples-gpu-95b9c58b6-nbg8g -- /bin/sh

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWw11jbpOdXbHQj9TicjDGCmUzTsu7f7I3wCwnjZNyWfRHicxtgaTc2vxYpwlbPiaKNeGJu1iakSWxvmw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

可以看到是一个A100

xinyu [ ~ ]$ kubectl get deployment

```
NAME          READY   UP-TO-DATE   AVAILABLE   AGEsamples-gpu   1/1     1            1           4m56s
```


将GPU Pod的副本数增加为2：

xinyu [ ~ ]$ kubectl scale deployment samples-gpu --replicas=2

deployment.apps/samples-gpu scaled

xinyu [ ~ ]$ kubectl get deployment

```
NAME          READY   UP-TO-DATE   AVAILABLE   AGEsamples-gpu   1/2     2            1           7m28s
```

过了1-2分钟，增加完毕：

xinyu [ ~ ]$ kubectl get deployment

```
NAME          READY   UP-TO-DATE   AVAILABLE   AGEsamples-gpu   2/2     2            2           11m
```

再次查看AKS节点，又多了一个GPU VM。

xinyu [ ~ ]$ kubectl get nodes

```
NAME                                STATUS   ROLES   AGE    VERSIONaks-gpu-spot-57p8w                  Ready    agent   10m    v1.27.9aks-gpu-spot-p9vh8                  Ready    agent   3m1s   v1.27.9aks-nodepool1-34768744-vmss000000   Ready    agent   63m    v1.27.9aks-nodepool1-34768744-vmss000001   Ready    agent   63m    v1.27.9aks-nodepool1-34768744-vmss000002   Ready    agent   63m    v1.27.9
```

查看karpenter对应的三个CRD：

xinyu [ ~ ]$ kubectl get crd |grep -i kar

```
aksnodeclasses.karpenter.azure.com               2024-03-24T01:18:01Znodeclaims.karpenter.sh                          2024-03-24T01:18:01Znodepools.karpenter.sh                           2024-03-24T01:18:01Z
```

查看karpenter claim的节点，有两个：

xinyu [ ~ ]$ kubectl get nodeclaims.karpenter.sh

```
NAME             TYPE                       ZONE              NODE                 READY   AGEgpu-spot-57p8w   Standard_NC24ads_A100_v4   southeastasia-2   aks-gpu-spot-57p8w   True    15mgpu-spot-p9vh8   Standard_NC24ads_A100_v4   southeastasia-2   aks-gpu-spot-p9vh8   True    8m11s
```

此时查看Azure VM，有两个GPU SpotVM：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWw11jbpOdXbHQj9TicjDGCm0wA7UhV9kFAlr3KsGhwMicialo08kicqDB3q3sHsl80wpBg9plbicQsVCA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWw11jbpOdXbHQj9TicjDGCm6RbUo66DLLXhf9gzQmaia2iaE8WE38ZvhxqicwkCWYCbn3SVqatv1wZBQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWw11jbpOdXbHQj9TicjDGCmeFxDGjeKBl2Sp0kKDdoarAoAb5kTUqTQSnHWDzv7hGx3uFrcv9xCqw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

将deployments副本数设置为0，AKS会剔除对应节点，Azure也会删除GPU SpotVM。

xinyu [ ~ ]$ kubectl scale deployment samples-gpu --replicas=0

```
deployment.apps/samples-gpu scaled
```

xinyu [ ~ ]$ kubectl get deployment

```
NAME          READY   UP-TO-DATE   AVAILABLE   AGEsamples-gpu   0/0     0            0           26m
```



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWw11jbpOdXbHQj9TicjDGCmkbwk71VUjQt4XC1TPrnULIHdWoAfZvkWeMbsZeOibKexnGxyDUwhTeQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWw11jbpOdXbHQj9TicjDGCmia1ZiaffDqU0ibeOctC3E8OvLibp9KXmictQicUZW0I9q10AwzORc8GiaicxhA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)