1. **什么情况会标记ECN?**



主要有三种原因：

- 拥塞
- out_of_sequence
- slow_restart



其中拥塞是ECN被标记的最常见原因。在这种情况下，ECN是被交换机标记的。



**2.非数据报文被标记ECN，网卡是否会回复CNP？**

write的ack报文以及read的read request报文，被交换机标记了ECN，网卡收到以后，依然会回复CNP。CNP会被回复给sender with ECN b'11。

 



**3.与ack相关的四个知识点**

在这些硬件计数器中，很多和ACK有关。我们先介绍一下ACK相关的内容。

**A.在有损RoCE网络下，当接收端有一个包没收到的时候，会向接收端发什么**

接收端向发送端发送两个包：oos_nack（out of sequence negative acknowledgment）、cnp（ECN标记产生的，让发送端降速）。



 **B. 接收端什么时候向发送端发ack/NACK?**

- 报文传完
- OOS（产生的原因是：收到两个psn，号不对）



**C.关于重传机制**

- ConnectX-4：从一个IB重传协议的丢失段重复传输，go-back-N。这可能会造成大量包重传
- ConnectX-5及以上。通过使用硬件重传来改善对丢包的反应
- ConnectX-6 Dx。使用一个专有的选择性重复协议



**D.在有损网络中，什么时候发送端重传？**

- 当发送端收到out-of-syquence（乱序）nack,重传。
-  最后一个报文丢包
-  Ack自己丢了
-  OOS nack丢包

 

后三种情况，需要依赖timer过期来重传。如果等timer过期，需要等很久，会增加延迟。adaptive timer原理是不用静态的timer过期，硬件自己来管。自己猜测，timer timeout自适应调小，来适应过期的时间。



 对于静态timer下，简单判断是：如果包重传的有点多，那就是timer out太小。如果丢包，那就是timer超时设置的太大。



上文OOS_NACK/NAK，比较形象的解释见下图下图。也就是说，Responder没收到Message2却收到了Messages3，因此发现PSN不对，因此对Requestor发Nak2。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo7Q9TtYHznIwBzwL08wMSoibZlkMd1XpeibU88DWFM99ia7BJ5A0OBycWEw/640?wx_fmt=png)



还有一种情况，由于超时，Ack1没有成功发到对端，因此对端需要重传Message1。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo7JPmb0k4icia3ZfWgxGvVXfSBh1rAPrIMXDLYXuLVzd4JiawJgsLs8BRlA/640?wx_fmt=png)





Service Type支持的IBV，我们看到RC支持的最全：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo7XIk2gCUI61ftqgDib6BiakZWKhnUwvdwdb8mNiaxDhxvpWzSo1cKfzWsA/640?wx_fmt=png)



**4.数据移动的两种技术**

Buffer Copy和Zero Copy（RDMA Read/Write）。

典型的buffer copy如下图所示：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo79lwG6AqmrTj38cHoxPmnOsIE90wNA53upK9X7xw51p12GkWAgVR8jw/640?wx_fmt=png)

典型的Zero Copy如下：



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo7c9Mic4ouc6RV0JHHacf1DGKEUbKwJLiaZG8OCKBAyjVwOS3uPVHmhRrQ/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo7BQcDHN8c99P9LSGticicc82z1fJSrM83ibeIGEeWknfKat3RAygQSwribA/640?wx_fmt=png)



我们对比一下BufferCopy和Zero Copy。前者使用Send的方式，后者使用RDMA Read/Write；前者适合小的message，后者适合大的message。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo7dxKxiaGsbPUxvUpg3ICqB4p6DSsd0TdZPDUE2r8qHx1ibDib5icUo8CKFg/640?wx_fmt=png)





**5.RDMA网络的优化点**

1.多打一

在发送端设置流控。

- 限制每次发送：8-16K
- 设置send window 128-512个packets
- 每1/2window时间，responder发送SW ACK。
- 一旦收到ACK，windows滑动。
- 将Read切分为32KB段。如果是1MB的read，将会由32个request完成。



2.资源管理优化

- 使用Send发小的message，使用Write/Read发大的message（8-16KB或者更高）
- 使用SRQ（Shared receive queue）来减少buffer。
- 在最近的NUMA分配buffer



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo7QhZMN2X2yiaBcGdiblPqdb1iaZ5icSg2zoDkNLIrHJ0F8tNCDz9Dd4rx1g/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo7snYgkIKHhubrIQdBFusUu2D3xHn6YHcecgdZsvDfLFz7GibZ6V1bH3Q/640?wx_fmt=png)









**6.网络中的几个概念**

先明确网络中的几个概念：RTT、传输时间、传播延迟。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMeS6iao2cyL1fzsAXuvaJlicz9EOOla430JD1qrNowJU944Bl8wRELgvnsme8tFn6ajyHVibes0tFg/640?wx_fmt=png)



**Socket API**

在以太网中，我们应用调用网络使用socket API，数据会涉及到从应用缓存到sockets、从sockets到tcp/ip、从tcp/ip到网卡driver的三层拷贝，因此效率较低。



如下图所示: socket libary位于用户态，被应用调用。在内核态，socket与TCP/IP对接，然后TCP/IP与Device Driver对接。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo7NFPBsZO4WtnR87QjSbWSjrY73fhibsTFicmE7Nu3O4tXeeMR3ia2MSXfg/640?wx_fmt=png)



SocketAPI如下图所示：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMeS6iao2cyL1fzsAXuvaJlGn6N3oAHwtbKztB5iaDA8glRiarH1MWJlUquUI9Y7qA46JQgKVJwxsLw/640?wx_fmt=png)

如果是RDMA的话，应用通过Verbs与RDMA Library对接，然后RDMA Library直接跳过kernel，与Nic对接。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo77zsXNsRBXcCacdPlj9gGs9t6BCjuXOuEJEhMEGOyHiafFTJHNFSGEkg/640?wx_fmt=png)



**7.RDMA的数据面和控制面**

而RDMA分为数据面和控制面，其控制面是过kernel的。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo7fAhZxIW5iaBUPLcOD8SWu6aJz2U73AaMVVZ3fkNTM73vhKBSicA1elaA/640?wx_fmt=png)

- 数据面有：Send、Receive、RDMA、Completion Resrieval、Request event。
- 控制面有：Resource setup、Memory management。



Memory Registration与Memory Regions有以下四个作用：

- Protection：Byte级别、Permission（R/W）
- Memory Pining
- Translation：Page level
- on demand paging option



如下图所示，RDMA是访问虚拟内存，虚拟内存与物理内存页有有转化的关系。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo76Mb6FYU5INocxSlnOYicWzS9KicdCO46VQ3mLONKKrkibmdzKoka82xgg/640?wx_fmt=png)



RDMA对于每个应用而言，有两个队列，如下图所示：

- QP：Send和Receive Queue
- CP: completion Queue

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo7DXL2ALxZHJQybJQPSaBYdicPHVox50Zhke57hjcDTAHN6mdBRiaNB4eQ/640?wx_fmt=png)

Protection Domain是为了隔离Memory Regions和QP（注意没有隔离CP）：



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo7lTeFWkTkAUZsK71rD06icxBibJib07UjBXcNh6w4aX6WibNLx65C8HwAfg/640?wx_fmt=png)

RDMA中的RC类似TCP，即可靠连接，如下图所示，消息发完后Responder发ACK给Requester：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW9zFRce9MCsAPnPVOIicKo7KZ3TviaYBGv2skMLv0v8DHtT616ibuPJcYK4ticKzXCyPXJjfcIibF8icCw/640?wx_fmt=png)







**8.RDMA发送端rp_cnp_handled数量增加**

```
测试方法是：使用编程手册重点rdma通信的sample，-send、recv模型
```

接收端未调用post send，发送端调用post send，之后两边poll cq

1、接收端app无反应

2、接收端counter变化：

7c7

< /sys/class/infiniband/mlx5_0/ports/1/hw_counters/out_of_buffer:3

\---

\> /sys/class/infiniband/mlx5_0/ports/1/hw_counters/out_of_buffer:4

3、发送端app出错：

mlx5: n136-096-142: got completion with error:

00000000 00000000 00000000 00000000

00000000 00000000 00000000 00000000

00000000 00000000 00000000 00000000

00000000 00008716 0a001f8e 000027d2

completion was found in CQ with status 0xd

got bad completion with status: 0xd, vendor syndrome: 0x87

poll completion failed

4、发送端counter变化：

10c10

< /sys/class/infiniband/mlx5_0/ports/1/hw_counters/req_cqe_error:5

\---

\> /sys/class/infiniband/mlx5_0/ports/1/hw_counters/req_cqe_error:6

18c18

< /sys/class/infiniband/mlx5_0/ports/1/hw_counters/rnr_nak_retry_err:3

\---

\> /sys/class/infiniband/mlx5_0/ports/1/hw_counters/rnr_nak_retry_err:4

24c24

< /sys/class/infiniband/mlx5_0/ports/1/hw_counters/rp_cnp_handled:43304

\---

\> /sys/class/infiniband/mlx5_0/ports/1/hw_counters/rp_cnp_handled:43305





问题。为什么nr_nak_retry_err和rp_cnp_handled在发送方会增长？



CQE status (0xd) 可以参考下面链接中的BV_WC_RNR_RETRY_EXC_ERR (13):

https://www.rdmamojo.com/2013/02/15/ibv_poll_cq/



**IBV_WC_RNR_RETRY_EXC_ERR (13)** - RNR Retry Counter Exceeded: The RNR NAK retry count was exceeded. This usually means that the remote side didn't post any WR to its Receive Queue. Relevant for RC QPs.



也就是说，rnr_nak_retry_err，这是因为 receiver没有向Receive Queue.发布足够的WR。



产生cnp原因，除了congestion 之外，还有两个可能会造成cnp的是out_of_sequence（简称oos）, slow_restart 。所以发送端是有可能在接收端没有cnp的时候，出现cnp计数的。所以要具体分析。





# **9.PFC风暴预防**

在RoCE网络中，PFC既是最后的手段，也应该预防。





![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWibL4Mib7GRB0mR7ysIRPLXXOo576yDko9kH8y5WClm9icJaWicZGP54nJgnQt9RQON6Dgj5mTZ0Sxuw/640?wx_fmt=png)

而PAUSE帧，是一定需要disable的。



默认情况下该参数打开，需要关闭：

[root@master ~]# ethtool -a ens1f0 |grep -i rx

RX:       on

[root@master ~]# ethtool -a ens1f0 |grep -i tx

TX:       on



[root@master ~]# ethtool -A ens1f0 rx off tx off



**PFC: 基于优先级的流量控制。**



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWibL4Mib7GRB0mR7ysIRPLXXfRDblqxDibjhcghYDmhdZ71nNib79SnfX01AXj3G7eHR82ZaM1KvMTpA/640?wx_fmt=png)

PFC有8个虚拟通道：



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWibL4Mib7GRB0mR7ysIRPLXXbkM75Oy5QTV1P2biazNlibGKhwkzwXmBOgN4C1kDgZToKgXJjse3RuHg/640?wx_fmt=png)



**PFC风暴预防**

在网卡意外地长时间无响应的情况下，流量控制机制可能会传播暂停帧，这将导致拥堵扩散到整个网络。



为了防止上述情况的发生，设备会持续监测其状态，试图检测它何时变得停滞。当设备停滞的时间超过预先配置的超时，流量控制机制（全局暂停和PFC）会自动禁用。



当PFC正在使用时，一个或多个优先级已经停滞，PFC将在所有优先级上被禁用。当设备检测到停滞已经停止时，流量控制机制将恢复其配置的行为。该配置是按物理端口进行的。如果不止一台主机在配置这个配置，将使用最后的配置。



**PFC风暴预防机制是如何工作的？**

它的工作方式很简单--在网卡上有一个计数器，当Rx缓冲区满时开始计数。当该计数器等于一个预先配置的值时，网卡就会停止流控机制。



当网络上正常发送RoCE无损流量，假设在某个时刻，发生了PFC风暴。



- T[rxb]是Rx缓冲区填满的时间。当网卡 Rx 缓冲区满时，NIC 开始发送暂停。
- T[sp] 是 NIC 设置 "风暴预防 "所需的时间。该时间的默认配置为 8 秒，可以通过向 "device_stall_critical_watermark "寄存器写入新的阈值(单位：毫秒)来修改。有效范围是100[ms] - 8[second]。注意，此时，NIC可能会发送暂停数据包。
- 当T[sp]过后，风暴预防开启，这意味着没有暂停，尽管缓冲区已满。



有两个有用的计数器，可以帮助我们监测和调试PFC风暴问题。

```
# ethtool -S ens1f0 |grep -i tx_pause_storm_warning_events     tx_pause_storm_warning_events: 0# ethtool -S ens1f0 |grep -i tx_pause_storm_error_events     tx_pause_storm_error_events: 0
```

- 'tx_pause_storm_warning_events' - 这个计数器表示设备停滞的时间超过了预先配置的'警告水印'（"device_minor_critical_watermark"）。它不一定意味着发生了'PFC风暴预防'。
- 'tx_pause_storm_error_events' - 这个计数器表示设备停顿的时间超过了预先配置的'关键水印'。当这个计数器增量时，确实意味着'PFC风暴预防'的发生。



参考下图，我们关注计数器在什么情况下增加：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWibL4Mib7GRB0mR7ysIRPLXXZeI2HwNdnrHm0JwAtzzic1K20mzHk5jQzibw03gTvQMGDyuwKxUJofSA/640?wx_fmt=png)

**我如何配置PFC风暴预防？**

PFC风暴预防默认启用，"device_stall_critical_watermark "被配置为8秒。你可以通过使用以下两种方法之一来修改这个阈值。

- sysfs方法

  将 "device_stall_critical_watermark "改为100[ms]：

  echo "auto" > /sys/class/net/eth*/settings/pfc_stall_prevention

- 将 "device_stall_critical_watermark "为8[秒]：

  echo "default" > /sys/class/net/eth*/settings/pfc_stall_prevention



- mlxreg工具

首先，使用下面的命令来读取PFCC寄存器：

mlxreg -d <PCI address> --reg_name=PFCC --get --indexes "pnat=0x0,local_port=0x1,ddbx_operation_type=0x0"



我们要修改的寄存器叫做 "device_stall_critical_watermark"，下面是应该使用的命令。

```
mlxreg -d <PCI地址> --reg_name=PFCC --indexes "pnat=0x0,local_port=0x1,ddbx_operation_type=0x0" -set "critical_stall_mask=0x1,prio_mask_tx=0xff,prio_mask_rx=0xff, device_stall_critical_watermark= xxx"
```



有效范围是0x64（=100ms）-0x1F40（8秒）。



请确保将 "device_stall_minor_watermark "寄存器的值设置为低于或等于 "device_stall_critical_watermark "寄存器。



如果想修改 "device_stall_minor_watermark "寄存器，可以通过使用下面的命令完成。

```
mlxreg -d <PCI address> --reg_name=PFCC --indexes "pnat=0x0,local_port=0x1,dcbx_operation_type=0x0" -set "minor_stall_mask=0x1,prio_mask_tx=0xff,prio_mask_rx=0xff,device_stall_minor_watermark= xxx
```



**10.灵魂拷问\*3@RDMA QPs**

**灵魂拷问1： 一个NVIDIA Mellanox网卡最大的QP数量是多少，有无推荐值？**

每个卡的最大qp数量是不同的，查看方法：

root@l-csi-13331s:~# ibv_devinfo -d mlx5_0 -v | grep max_qp

​    max_qp:             131072

​    max_qp_wr:           32768

​    max_qp_rd_atom:         16

​    max_qp_init_rd_atom:      16



***\*# ibv_devinfo -d mlx5_0 -v | grep max_qp\**
    \**max_qp:             262144\****

查看当前qp的使用情况，有两个qp在使用：

```
root@l-csi-13331s:~#  ls /sys/kernel/debug/mlx5/0000\:03\:00.1/QPs0x146  0x147root@l-csi-13331s:~# cat /sys/kernel/debug/mlx5/0000\:03\:00.1/commands/CREATE_QP/n65root@l-csi-13331s:~# cat /sys/kernel/debug/mlx5/0000\:03\:00.1/commands/DESTROY_QP/n63
```

我们也可以运行如下命令行查看qp的使用情况：



```
# /opt/mellanox/iproute2/sbin/rdma res0: mlx5_0: pd 1 cq 2 qp 1 cm_id 0 mr 0 ctx 01: mlx5_1: pd 1 cq 2 qp 1 cm_id 0 mr 0 ctx 0
```



或者



```
# /opt/mellanox/iproute2/sbin/rdma resource show qplink mlx5_0/- lqpn 1 type GSI state RTS sq-psn 0 comm [ib_core]link mlx5_1/- lqpn 1 type GSI state RTS sq-psn 0 comm [ib_core]
```





关于qp使用的建议值，这没有定论。但通常我们会建议客户使用不要超过1000个。qp使用太多，会对congestion control的控制力造成影响，而且也会存在 qp context 占用大量 cache 导致 cache miss 而影响性能。





**灵魂拷问2：VF LAG策略是HW Hash，多个QP依据五元组去选physical port。什么是五元组？还有其它什么元组？**



关于曾经遇到的QP选择PF的问题，请参照：

[从Driver源码分析RDMA问题](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663510592&idx=1&sn=1c99a58cfbd34df73e31adb8ba139de1&chksm=81d6b538b6a13c2e89f0ea6a0e36a5ec92eb428882a6f9590575fd3e75b15f6e85ee593e678a&scene=21#wechat_redirect)



**https://blog.csdn.net/whatday/article/details/84285434**

首先先看几个定义：

（1）IP地址：即依照TCP/IP协议分配给本地主机的网络地址，两个进程要通讯，任一进程首先要知道通讯对方的位置，即对方的IP。
（2）端口号：用来辨别本地通讯进程，一个本地的进程在通讯时均会占用一个端口号，不同的进程端口号不同，因此在通讯前必须要分配一个没有被访问的端口号。
（3）连接：指两个进程间的通讯链路。
（4）半相关：网络中用一个三元组可以在全局唯一标志一个进程：
（协议，本地地址，本地端口号）
这样一个三元组，叫做一个半相关,它指定连接的每半部分。
（5）全相关：一个完整的网间进程通信需要由两个进程组成，并且只能使用同一种高层协议。也就是说，不可能通信的一端用TCP协议，而另一端用UDP协议。

因此一个完整的网间通信需要一个五元组来标识：（协议，本地地址，本地端口号，远地地址，远地端口号）
这样一个五元组，叫做一个相关（association），即两个协议相同的半相关才能组合成一个合适的相关，或完全指定组成一连接。


（6）协议号:IP是网络层协议，IP头中的协议号用来说明IP报文中承载的是哪种协议,协议号标识上层是什么协议（一般是传输层协议，比如6 TCP，17 UDP；但也可能是网络层协议，比如1 ICMP；也可能是应用层协议，比如89 OSPF）。

TCP/UDP是传输层协议，TCP/UDP的端口号用来说明是哪种上层应用，比如TCP 80代表WWW，TCP 23代表Telnet，UDP 69代表TFTP。

目的主机收到IP包后，根据IP协议号确定送给哪个模块（TCP/UDP/ICMP...）处理，送给TCP/UDP模块的报文根据端口号确定送给哪个应用程序处理。



**三元组是**：

协议，本地地址，本地端口号

**四元组是**：

​    源IP地址、目的IP地址、源端口、目的端口

 

**五元组是:**
   源IP地址、目的IP地址、协议号、源端口、目的端口


**七元组是:**

​    源IP地址、目的IP地址、协议号、源端口、目的端口，服务类型以及接口索引。

目前RoCE网络中用的是五元组，我们查看抓包：

Internet协议层。有源和目标IP、DSCP、ECN标志位。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1jaBcu273icF5sQWSlClq0n3aF31epgibzEh5sKq5cggbYczmIj5btN3g/640?wx_fmt=png)

查看UDP数据报协议层，可以看到源和目标的Port：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1KiaFwib5dVO2wpUsfbWthk1mWscqZr7Y7eV12scAQu2pN4rCUXExrxHQ/640?wx_fmt=png)

当然，在RoCE的包中，除了五元组的信息，还有很多IB协议相关的信息，如：

查看Infiniband层：RC模式、RDMA READ Request、目标QP、虚拟地址、Remote Key等信息。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1ibLOMWI6TlnMLQOESERBvakTibuibgkGKAr9H6iaVecVbicrjTLWbNGd4DQ/640?wx_fmt=png)





**灵魂拷问3. 默认情况下，Linux系统中dmesg不打印qp相关信息，如何在dmesg中显示dmesg相关信息？**



默认情况下，OFED的驱动不打印QP的信息，我们可以通过修改编译OFED的驱动来实现。

```
  #mkdir /david/david  #cd /usr/src/mlnx-ofed-kernel-5.4/  #cp -Rp ./* /david/david  #cd /david/david  #vi ./drivers/infiniband/hw/mlx5/qp.c
```

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXm93bGkz6KicCTSAX0jVXLz4qJ66HyNfeX0K2xACLDTKtrwcMCzUMQp41icsicN10vQne8STTUgwmnQ/640?wx_fmt=png)

```
root@/david/david# /etc/infiniband/infoprefix=/usrKernel=4.9.0-13-amd64grep: /lib/modules/4.9.0-13-amd64/build/drivers/infiniband/core/Makefile: No such file or directoryConfigure options: --with-core-mod --with-user_mad-mod --with-user_access-mod --with-addr_trans-mod --with-mlxfw-mod --with-mlx5-mod --with-ipoib-modroot@/david/david# ./configure --with-core-mod --with-user_mad-mod --with-user_access-mod --with-addr_trans-mod --with-mlxfw-mod --with-mlx5-mod --with-ipoib-mod
```

\# make -j8

\#make install

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXm93bGkz6KicCTSAX0jVXLzx9nf48Hb42OCqAhG4iaoppL2RBDOSBBAibCfibssELCh7pWicoqkuYLBKQ/640?wx_fmt=png)



然后重启驱动：

```
# /etc/init.d/openibd restartUnloading HCA driver:                                      [  OK  ]Loading HCA driver and Access Layer:                       [  OK  ]
```

在dmesg中查看信息，我们可以看到qp相关的信息：

```
[228549.726084] lqpn = 329 (0x149), rqpn = 328 (0x148), fl = 107912 (0x1a588), udp_sport = 58766 (0xe58e)[228549.726118] lqpn = 328 (0x148), rqpn = 329 (0x149), fl = 107912 (0x1a588), udp_sport = 58766 (0xe58e
```





# **11.RDMA连接超时时间**

**RDMA CM**

通过RDMA的verbs接口，我们可以创建不同类型的QP，包括：

- RC: Reliable Connection，可靠连接，可以理解为基于msg的TCP实现
- UC: Unreliable Connection，不可靠的连接，但和RC一样，需要握手
- UD: Unreliable Datagram，不可靠数据报，类似UDP
- RD: Reliable Datagram，可靠数据报。

 

RC和UC都是基于连接的，需要建联操作，该操作可以通过RDMA CM库完成。

 

UD目前仅支持RDMAsend/recv语义，相较于write/read语义的延时稍高。比较适合探测场景，比如rping，RDMA CM也是基于UD实现的。



RDMA CM主要实现包含在ib_cm内核模块中，用户态的librdmacm只是一个agent，基于cm event进行驱动，如下图所示：



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUgicSWuhibWp7hEpp0uTicNvG9ASMOnn5m7dlQzk99icWWSlxuUlQ7VCBFpQQGr8icSg6P2RLDudf9aag/640?wx_fmt=png)

查看cm相关的内核模块：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUgicSWuhibWp7hEpp0uTicNvGiaUQKjgAaia3FZatHYEI8zyVQwxZLLAYm7BpYboFksanOdb2oaKnSOkw/640?wx_fmt=png)

 

 

关于rdma_cm的详细解释如下：

- The RDMA CM is a communication manager used to setup   reliable, connected and unreliable datagram data transfers. It provides an   RDMA transport neutral interface for establishing connections. The API   concepts are based on sockets, but adapted for queue pair (QP) based   semantics: communication must be over a specific RDMA device, and data   transfers are message based.

 

RDMACM是一个通信管理器，用于设置rc和ud数据传输。它为建立连接提供了一个RDMA传输中立接口。rdmacm这个API概念是基于socket的，但适应于基于队列对（QP）的语义：通信必须通过一个特定的RDMA设备，数据传输是基于message的。

 

- The RDMA CM can control both the QP and communication   management (connection setup / teardown) portions of an RDMA API, or only   the communication management piece. It works in conjunction with the verbs   API defined by the libibverbs library. The libibverbs library provides the   underlying interfaces needed to send and receive data.

 

RDMACM可以控制RDMA API的QP和通信管理（connectionsetup / teardown）部分，或者只控制通信管理部分。它与libibverbs库所定义的 verbs API一起工作。libibverbs库提供了发送和接收数据所需的基础接口。

 

- The RDMA CM can operate asynchronously or   synchronously. The mode of operation is controlled by the user through the   use of the rdma_cm event channel parameter in specific calls. If an event   channel is provided, an rdma_cm identifier will report its event data   (results of connecting, for example), on that channel. If a channel is not   provided, then all rdma_cm operations for the selected rdma_cm identifier   will block until they complete.

 

RDMACM可以异步或同步地运行。操作模式是由用户通过在特定调用中使用rdma_cmevent channel参数来控制的。如果提供了一个eventchannel，rdma_cm标识符将在该channel上报告其事件数据（例如，connecting的结果）。如果没有提供channel，那么所选rdma_cm标识符的所有rdma_cm操作将被阻止，直到它们完成。

 

 

使用RDMA CM的好处是：

- 避免重复性的工作
- 经过生产环境验证的细节实现，如可靠传输、超时机制等
- 生命周期比用户态长，可以较为妥善解决进程异常关闭场景的断连问题

 

除常规的建连/断连类的操作外，RDMA CM还封装了一系列的verbs接口：

- 创建/销毁memory region
- 创建/销毁qp和cq
- 获取CM事件

总体而言，CM是在尽可能模拟TCP和UDP的操作。

 

 

查看 ib_cm的代码架构：



```
static struct ib_cm {spinlock_t lock;struct list_head device_list;rwlock_t device_lock;struct rb_root listen_service_table;  u64 listen_service_id;/* struct rb_root peer_service_table; todo: fix peer to peer */struct rb_root remote_qp_table;struct rb_root remote_id_table;struct rb_root remote_sidr_table;struct idr local_id_table;  __be32 random_id_operand;struct list_head timewait_list;struct workqueue_struct *wq;/* Sync on cm change port state */spinlock_t state_lock;} cm;
```



那么，如果rdma连接出现问题，多久会timeout？因为我们不希望rdma cm长时间hang。因此当出现连接问题的时候，需要考虑timeout。即rdma_connect timeout



 

**RDMA_CM connect timeout**



我们先看RDMA CM连接超时的两个常见案例。

案例1。客户端发送了一个连接请求，但服务器从未收到它。

例如，由于交换机丢弃了数据包。

在这种情况下，第一次尝试和其他重试之间没有区别。

total_timeout = first_timeout_ms* retry_cnt

 

案例2。客户端发送了一个连接请求，服务器在驱动/内核层面上收到了该请求，但是实际的服务器应用程序不接受。

例如，如果应用程序被卡住或由于CPU过载而无法运行。

total_timeout = first_timeout_ms + not_first_timeout_ms * (retry_cnt -1)



 

公式列出来了，那么两种情况下默认的超时时间是多少呢？

默认值：retry_cnt：cma_max_cm_retries 15

Case1 - 服务器从未收到连接请求。

total_timeout = 18432 msec*15 ~= 300msec = 5 min

Case2 - 服务器收到连接请求，但应用程序不接受。

total_timeout = 18432 msec + 67854ms *14 = 968,388 ms = 16min



接下来我们看子公式：

first_timeout_ms =

cm_convert_to_ms(packet_life_time) * 2 + cm_convert_to_ms(remote_cm_response_timeout);



not_first_timeout_ms =

cm_convert_to_ms(service_timeout) + cm_convert_to_ms(cm_id_priv->av.timeout);



显然和超时时间最相关的两个参数是：

- remote_cm_response_timeout
- cma_max_cm_retrie



目前这两个参数尚未开放修改的API。



https://elixir.bootlin.com/linux/v4.10/source/drivers/infiniband/core/cm.c

https://blog.lucode.net/RDMA/rdma-cm-introduction-and-create-qp-with-external-cq.html

https://www.rdmamojo.com/2013/01/12/ibv_modify_qp/

 



**12.RoCE丢包选择重传不好使**

我通过通过一个交换机将两个服务器连接，通过perftest做1打1.

交换机可以设置为每隔几个数据包就丢一个数据包，从而模拟数据包丢失。



首先确认两个节点的RoCE的重传参数已经打开：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXicaYQYGq1DU5t26NDrzHRMHBEKk4O74vMqsxjb3yK7g6ib2L7Nu4qF5nup6lZh57FmueZlBjUehHQ/640?wx_fmt=png)

然后通过ib_send_bw做压力测试，在client端通过tcpdump收信息，形成.pcap文件。



我们查看分析结果。

在下图中PSN 7395的下一个是是7397。7396没发过去。当当7396未发送成功的消息发给发送端的时候，包已经发到了7408。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXicaYQYGq1DU5t26NDrzHRMs0OWXYB3AuV8ibjwaUEH8xoTemKPZ6W87z2PGcQ2EPlMv8qkhZ7AlXQ/640?wx_fmt=png)

接下来我们看重传。OOS发生后，重传不是只重传7396，而是重传了7396到7408全部重传，这是go-back N。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXicaYQYGq1DU5t26NDrzHRMCmFbyf59vaoIr4MqPpVobeGACBDHhq5q4A19Eic0r8UHmKV93kQMicxA/640?wx_fmt=png)

那么，是选择重传不好使么？



不是的。

接下来我们看ib_write_bw的结果分析。

在下图中，143明显是选择性重传：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXicaYQYGq1DU5t26NDrzHRMOjrPmQpe4ccQ3Afwc9YoAOu1pOeMG87nuGlc37SQetGkyiaStVrY7HQ/640?wx_fmt=png)



为何第一个图不是选择重传呢？



因为选择重传只对RDMA Read/Write有效，对IB send/receive无效。



RDMA Write选择重传的实现机制：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXicaYQYGq1DU5t26NDrzHRM08HW1KFz66Ik8HVFVVvqUX6AySPx0Wg16FOPwh4YGBBiah2xmSfnKgA/640?wx_fmt=png)

RDMA Write 重传的实现机制：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXicaYQYGq1DU5t26NDrzHRMwPQh1YbDJW97uFDNmg0ZlTdnze6z1wHVSAUMa7evetvoVRh9ZXro3Q/640?wx_fmt=png)

那么，重传的时候，都重传哪个PSN的包呢？

有两个：

- 丢失的PSN包；
- 当前transmit window最后一个PSN包：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXicaYQYGq1DU5t26NDrzHRMNSzvrpicLicPZvoB3T0T9AwVJbPZ0QEqxiaXQtOwxj6eD9xyXPborDrNA/640?wx_fmt=png)



enable的方法：

mlxconfig -dset RDMA_SELECTIVE_REPEAT_EN=0x1 

mlxfwreset -d-y reset

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXicaYQYGq1DU5t26NDrzHRM0pMGnlicZj0kDHBlu6AunSa78kibpW27PA85FUkRvqteNjDR8MhtVsMQ/640?wx_fmt=png)



**13.澄清！网络加速QoS Priority的几个概念**



网卡自身的优先级有PCP（ Priority Code Point，二层）和DSCP（ Differentiated Serviced Code Point, DSCP，三层）。



PCP优先级是从0-7，7最高，0最低：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVaLopL2SwOYib9dpS5ym7RYlweKgC2ox5xy0YBThuyEeJziccSg4eNtWiatvYP2KG5UHZsicAKJCCCtA/640?wx_fmt=png)

默认情况下，TCP的流量走Priority0, RoCE流量走Priority3。



但如上文所述，PCP是二层协议，实际生产一般用三层的DSCP。那么，DSCP与PCP如何对应？

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVaLopL2SwOYib9dpS5ym7RYYR7Mt2IfbMSpYPYbu4GGHu11pwkXFA5VDuZ8y4L7S9PicyRnwWRZFOw/640?wx_fmt=png)

还有个和优先级相关的，叫tc(**Traffic Control**)。

[从原理到实现：网络I/O卸载](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663510562&idx=1&sn=254ab449668437dc7dfe5a25540ce7d7&chksm=81d6b55ab6a13c4c1914150b893582acbfaf681d8253211fa5f2626e0a79eaf56424727e3c59&scene=21#wechat_redirect)

TC最初是在Linux Kernel出现的，为的是Linux中的QoS。在4.9~4.14内核，Linux终于增加了对TC Flower硬件卸载的支持。也就是说OpenFlow规则有可能通过TC Flower的硬件卸载能力，在硬件（主要是网卡）中完成转发。OpenVSwitch在2018年增加**了对TC Flower的支持。**



在OVS-TC中，严格来说，现在Datapath有三个，一个是之前的OVS kernel datapath，一个是位于Kernel的TC datapath，另一个是位于网卡的TC datapath。位于kernel的TC datapath一般情况下都是空的，它只是ovs-vswitchd下发硬件TC Flower规则的一个挂载点。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVaLopL2SwOYib9dpS5ym7RYic3qnk3QiaVRtiaHp5sPR9oQuicjVTHduia1ErBkcfibRqJjibAQTwkDwN6cw/640?wx_fmt=png)

使用OVS-TC方案，可以提供比DPDK更高的网络性能。因为，首先网络转发的路径根本不用进操作系统，因此变的更短了。其次，网卡，作为专用网络设备，转发性能一般要强于基于通用硬件模拟的DPDK。



如果是基于OVS-kernel的网络卸载，规则的添加有两种方式：

1.创建OVS-kernel，将PF、VF代表口都添加上，OVS中默认的规则就可以转发。也能够看到流量被卸载。卸载的时候，会转到tc下硬件。

2. 不通过OVS-Kernel通过TC直接引流，将流量引到VF上。



OVD-DPDK的offload不使用tc，而是使用rte-flow直接下硬件了。



那么，TC与PCP的关系如何对应？如下图所示，需要注意的是，tc和0,1和PCP的0,1是反着对应的。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVaLopL2SwOYib9dpS5ym7RYCCuqCxQqwVcMb1zop3VnRAexwjrABYPEuB96Jzial0ls5kZwXkAiaaXA/640?wx_fmt=png)



除了上面介绍的PCP、DSCP、TC外，还有两个和qos相关的概念：ToS和tclass（traffic_class）。



在硬件驱动中，IP头部的ToS字段(8bit)会直接被赋值为traffic_class（0~255），而DSCP只是ToS字节中的高6位（值0~63）。

从上面信息我们可以看出：

tclass和ToS是一回事。rdma_cm时候用tos  vpi verbs时候用tclass。

应用通过rdma_set_optin函数来设置ToS值。

在硬件驱动中，根据设置的ToS到DSCP值的映射表，将ToS转换成DSCP值。

最终根据DSCP值到TC的映射表来将网络流映射到对应的TC上，然后下网卡硬件。



tclass-->tos---->dscp或者pcp---->tc



根据以上的一系列信息，大魏做个一个原创的对应图：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVaLopL2SwOYib9dpS5ym7RYtTl4rs7rBXu4lEDTDHMtZF4SnboOZEHoYQ8Y2iakdDYbEBnXCCwjsxA/640?wx_fmt=png)



那么，为什么我要介绍tclass呢。因此我们会用到，例如perftest的时候：



Server side.

 \# ib_write_bw --tclass=106-a -d mlx5_0

 Client side.

\#ib_write_bw-a -F10.7.159.71--tclass=106-dmlx5_0--report_gbits



我指定的是tclass 106，根据上表，我们就能迅速查到，它对应PCP3，也就是TC3，也就是默认RoCE走的优先级，是不是很方便？



如果坚持计算ToS到DSCP的一一对应关系，而不是区间映射，那么以如下这行为例：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVaLopL2SwOYib9dpS5ym7RYvdST2Lfwu7e1K4KICXhhGiaANlMZsaW45UPhImbib506n9iaaicK4sSXnQ/640?wx_fmt=png)

tclass是32个数字，dscp是8个数字。那么对应关系表就是：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVaLopL2SwOYib9dpS5ym7RYvqle5fRN32HlAx0bSFR50o9Adiah6ibSbN7MpGeoghTQOXhopS1a9a2A/640?wx_fmt=png)

在平时的工作中，我们只需要知道tos/tclass对应的PCP和TC级别就可以了。



除了上面在perftest中指定tclass，还有一个方法是在配置中指定tclass，也就是让所有roce流量走某一个tclass，如：

\# cat /sys/class/infiniband/mlx5_0/tc/1/traffic_class
Global tclass=105

为端口上的所有RoCE流量设置全局TClass为106（DSCP 26），注意这是一个全局强制值，将应用于所有QP，优先于cma_roce_tos设置和用户应用指定的值。



按照上表查看，105对应pcp3和tc3。也就是默认的优先级3。如果我们要反设置这个值：

\#echo -1 >/sys/class/infiniband/mlx5_0/tc/1/traffic_class 



那么，我们有没有方法针对tc上设置流量百分比呢？

可以的。

一个流量类(TC)可以被赋予不同的服务质量属性，分别有：

l 严格优先级(Strict Priority)

l 最小带宽保证(Enhanced TransmissionSelection, ETS)

l 速率限制(Rate Limit)

下面我们针对ens255f0这个网卡进行设置：

```
#  mlnx_qos -i ens255f0 --trust=dscp#  mlnx_qos -i ens255f0 --pfc 0,0,0,1,0,0,0,0#  mlnx_qos -i ens255f0 -s ets,ets,ets,ets,ets,ets,strict,ets -t 0,0,50,50,0,0,0,0
```

设置结果如下：

\# mlnx_qos -i ens255f0

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVaLopL2SwOYib9dpS5ym7RY6OOQX3QxDZ5ZsjkZcgMSJgqSJKvdJnW6ABPEAkaI8X4Eib4eibznbomg/640?wx_fmt=png)



**14.RDMA中的DCT传输模式**

RDMA传输的四种基本类型是：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbOyhhE7xpdhFicFzxQO3BDukndibEdOSnaUPobHchfAeE8krCWgqMy62w/640?wx_fmt=png)

四种IBA Operations如下：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbB0mIjPA3mb9uPRgwVNAYF8XcjHViaaWMibCOibS88JuWsicG6qbJhCDuyA/640?wx_fmt=png)

不同的服务类型，对于IBA Operations的支持是不同的。RC是四种都支持。UD支持IBA中的Send&Receive。默认用RC比较多。



但RC模式下，当QP的数量大量使用时（数千个），性能会下降。所以，RC模式不利于超大规模部署。UD虽然支持大规模部署，但是只支持IBA中的Send&Receive。



因此，RDMA在大规模使用时有两个切实的需求：

1.支持超大规模部署。

2.支持所有IBA操作。



为了同时满足以上两个诉求，业内提出DCT（Dynamically Connected Transport）概念。



对传输服务的扩展，能够实现更高的可扩展性，同时保持稀疏流量的高性能。利用DC传输可以减少全系统所需的QP总数，通过让可靠类型的QP动态地与任何远程节点连接和断开。



DCT Verbs和RDMA-Core Verbs的对比：

https://docs.nvidia.com/networking/display/rdmacore50/Dynamically+Connected+(DC)+QPs

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbuGkabM0yIyAK4ERcd6zvo4ic3qdzZsVNofRzicmoncpiaHySNjv7fLu0g/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gblSyPLQCLarIGFAfaKVxbwribzcUX859Up2AA1eGx1IaRAiciaX9Usx5IQ/640?wx_fmt=png)



RC每个目的是一个连接，所以扩展性上不去。DC支持IBA Operations的能力与RC是相同的。它的高扩展性是因为一个QP可以与多个目标通讯，这点类似UD的方式。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbuJ68iaNHISqo6LNoCP6ogwiaYdHFWVqw8oUa4vibPHGQbRibk4UphMmBicA/640?wx_fmt=png)







![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbXe4GcLqpFpXdUrARsPNk6wYhxQIZsjNYicgUZg0aYZueuVmVwG0Ge3g/640?wx_fmt=png)



一个DC的initiator可以连接任何DC Target。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbkCtasdwJ3rf1y9cJ4w1OCMVjyGyia7yL3SkicLTOKdLuqEBr2I702epg/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbibpbSIa1RlFlk8BlXZcAKxuTnZboBLsNZQyqGPqyoK1xFgvtQmWVfvg/640?wx_fmt=png)





![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbnz5Ok8J1EkMR1IobgkOz9pYaia9ib7Oy9oh18nKEuh5octeQsa9VK9dQ/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbnO6YasHfjA0XnEMbUAx3IQIKUpOOdhkZJ8uh7NsL9aGNicajADe9haw/640?wx_fmt=png)





![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbia4ZibTaC1yicHlHicM4zF1xDnuia4DWaJCVibhDhlgXX29XsfjR8eQxFRoA/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbZzlw8KOyT4qvRSDiaItV8XkcrO1UFor0kuThRF9j7fG2A82BLicS1ykw/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbGXxeFS37Yc7y5o5GpNZrX5emfQX0zs8GyMqOreFSJ2VOEvfw04P5DA/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbmPFw2JheaOQgUqp4UsoXiaVdoyibzibssQvKThJZpyEBZGdsSG8cDPzeQ/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbd3BmtjIJts1GmIrjnxYmt8RgcToHIlaUPtKfiaEAicFPRRmtnlrNg09Q/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbzptXQYUna3pR3dLOZd0JDvFnAS7VFDUiagkTALZqvrUuTq2w4BxiawVQ/640?wx_fmt=png)

DC可以切换目的地。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbF1JtIuPQ86JSlMYwDEfUXvkI3a6RD15lGDQftQfibMO2iajyKHqSyYYA/640?wx_fmt=png)





![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbod9D2KVEA7M8DTbdOj2Iqf65DudkJCGlRuQdvfYkYNDqPLcv4yMibRA/640?wx_fmt=png)

DC采用类似TCP的三次握手方式：



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gb3ndJONRPsI7OISbtUMdjkAroGRLLSmERZdBffJeSF0CZQQqWFv4tdw/640?wx_fmt=png)







![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbh0edAnA7z2icYPgF3SUklmOf2QtOMnOjpqIYg3UIfggzTQhe8W57Fpg/640?wx_fmt=png)











![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gb8heicU6vJ7VB1kM3e3Ot7RNKzJHfibD82rLoDZv68j94x1YiaR8YMyR7w/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbedJoLorvVIbicIlOJxylqdClMziaYtzGlJEWX0TG2LVQmEicfjYQMnFqg/640?wx_fmt=png)



·

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gbI9tvsf8AAl4027w9ZURHCJBF74KTssT3ugEtLcsVLNmwLtQ3gRx6RA/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWSZjqkXxAiabfmzdpexG4gb4r1dchIWWb7J1kialVPAeYEqDIUibSkdetyzgZ1DMf4z56aB3UlJrfUA/640?wx_fmt=png)



**
****15.灵魂拷问\*5：ibv_exp_reg_mr何在？**

在OFED4中，ibv_exp_reg_mr这个函数是可以被调用的 (**并不代表推荐使用！**)。它的作用是： Register a physical memory region from the user space，即从用户空间注册一个物理内存区域。



其结构为：

```
struct ibv_exp_reg_mr_in in = {0};/* Set IBV_ACCESS flags */my_access_flags = IBV_ACCESS_LOCAL_WRITE |\IBV_ACCESS_REMOTE_READ |\IBV_ACCESS_REMOTE_WRITE |\IBV_ACCESS_REMOTE_ATOMIC |\IBV_EXP_ACCESS_PHYSICAL_ADDR;/* Allocate a physical MR - allowing access to all memory */in.pd = pd;in.addr = NULL; // Address when registering must be NULLin.length = 0; // Memory length must be 0in.exp_access = my_access_flags;physical_mr = ibv_exp_reg_mr(&in);
```

从上面代码我们可以看出，ibv_exp_reg_mr有如下几个EXP：

- IBV_ACCESS_REMOTE_READ |\
- IBV_ACCESS_REMOTE_WRITE |\
- IBV_ACCESS_REMOTE_ATOMIC |\
- IBV_EXP_ACCESS_PHYSICAL_ADDR;



上面最常用的EXP是IBV_EXP_ACCESS_PHYSICAL_ADDR。



**灵魂拷问1：ibv_exp_reg_mr在OFED 5.0/5.2/5.4中是没有的，为什么呢？**

因为ibv_exp_reg_mr存在一定的安全隐患，因此没有被包含在rdma-core中。当使用PA-MR时，用户绕过了内存保护的内核机制，如果使用不当，可能会使系统崩溃。





**灵魂拷问2：如果我们要用户空间注册一个物理内存区域，怎么办？**

在OFED5中，我们需要使用virtual memory regions，而不是直接注册PHYSICAL_ADDR。因此OFED5中不提供可以注册物理内存地址的函数。



**灵魂拷问3：想要注册内存，在OFED5中如何实现？**

要使用malloc、calloc、memalign等分配的内存缓冲区，并使用该函数返回的虚拟地址，而不是使用内存物理地址。



具体而言，使用ibv_reg_mr取代ibv_exp_reg_mr。两者参数和标志相同，但前者没有IBV_EXP_ACCESS_PHYSICAL_ADDR标志。



我们看一下ibv_reg_mr函数的源码结构：

https://github.com/linux-rdma/rdma-core/blob/master/libibverbs/man/ibv_reg_mr.3

```
struct ibv_mr *ibv_reg_mr(struct ibv_pd " "*pd" ", void " "*addr" , " size_t " "length" ", int " "access" );
```

如果想要了解更为详细的ibv_reg_mr解释，请参考：

https://www.rdmamojo.com/2012/09/07/ibv_reg_mr/

**ibv_reg_mr()** registers a Memory Region (MR) associated with a Protection Domain. By doing that, allowing the RDMA device to read and write data to this memory. Performing this registration takes some time, so performing memory registration isn't recommended in the data path, when fast response is required.



翻译如下：

ibv_reg_mr()注册一个与保护域（PD）相关的内存区域（MR）。通过这样做，允许RDMA设备读取和写入数据到这个内存。执行这个注册需要一些时间，所以当需要快速响应时，不建议在数据路径上执行内存注册。



**灵魂拷问4：那么，****什么是MR、什么是PD？**

MR全称为Memory Region，指的是由RDMA软件层在内存中规划出的一片区域，用于存放收发的数据。IB协议中，用户在申请完用于存放数据的内存区域之后，都需要通过调用IB框架提供的API注册MR，才能让RDMA网卡访问这片内存区域。由下图可以看到，MR就是一片特殊的内存而已：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDIyN2GP2icuR75M4RmwPFu5t3ricAhYkqffW68FOWv3U2niaaQic8jo86Pg/640?wx_fmt=png)

在对IB协议进行相关描述时，我们通常称RDMA硬件为HCA（Host Channel Adapter， 宿主通道适配器），IB协议中对其的定义是“处理器和I/O单元中能够产生和消耗数据包的IB设备”。

## 为什么要注册MR

下面我们来看一下MR是如何解决本文开篇提出的两个问题的：

### 1. 注册MR以实现虚拟地址与物理地址转换

我们都知道APP只能看到虚拟地址，而且会在WQE中直接把VA传递给HCA（既包括本端的源VA，也包括对端的目的VA）。现在的CPU都有MMU**（memory management unit，内存处理单元）**和页表这一“利器”来进行VA和PA之间的转换，而HCA要么直接连接到总线上，要么通过IOMMU/SMMU做地址转换后连接到总线上，它是“看不懂”APP提供的VA所对应的真实物理内存地址的。

所以注册MR的过程中，硬件会在内存中创建并填写一个VA to PA的映射表，这样需要的时候就能通过查表把VA转换成PA了。我们还是提供一个具体的例子来讲一下这个过程：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nU3HCPzcrZU03jDLoyWASgEibFpSpOle4dMaIPTmRraqicIPeyPxZtvmAJgx5fppJiawQHGwgEZFWjdQ/640?wx_fmt=png)

现在假设左边的节点向右边的节点发起了RDMA WRITE操作，即直接向右节点的内存区域中写入数据。假设图中两端都已经完成了注册MR的动作，MR即对应图中的“数据Buffer”，同时也创建好了VA->PA的映射表。

1. 首先本端APP会下发一个WQE给HCA(**其实就是卡**)，告知HCA，用于存放待发送数据的本地Buffer的虚拟地址，以及即将写入的对端数据Buffer的虚拟地址。
2. 本端HCA查询VA->PA映射表，得知待发数据的物理地址，然后从内存中拿到数据，组装数据包并发送出去。
3. 对端HCA收到了数据包，从中解析出了目的VA。
4. 对端HCA通过存储在本地内存中的VA->PA映射表，查到真实的物理地址，核对权限无误后，将数据存放到内存中。

对于右侧节点来说，无论是地址转换还是写入内存，完全不用其CPU的参与。

### 2. MR可以控制HCA访问内存的权限

因为HCA访问的内存地址来自于用户，如果用户传入了一个非法的地址（比如系统内存或者其他进程使用的内存），HCA对其进行读写可能造成信息泄露或者内存覆盖。所以我们需要一种机制来确保HCA只能访问已被授权的、安全的内存地址。IB协议中，APP在为数据交互做准备的阶段，需要执行注册MR的动作。

而用户注册MR的动作会产生两把钥匙——L_KEY（Local Key）和R_KEY（Remote Key），说是钥匙，它们的实体其实就是一串序列而已。它们将分别用于保障对于本端和远端内存区域的访问权限。下面两张图分别是描述L_Key和R_Key的作用的示意图：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nU3HCPzcrZU03jDLoyWASgEFaEzX27qhONFiapCv12hghnG0ibeIaCXdF3JBedgnf90ovpnPoSlEafA/640?wx_fmt=png)

这里大家可能会有疑问，本端是如何知道对端节点的可用VA和对应的R_Key的？其实两端的节点在真正的RDMA通信之前，都会通过某些方式先建立一条链路（可能是Socket连接，也可能是CM连接）并通过这条链路交换一些RDMA通信所必须的信息（VA，Key，QPN等），我们称这一过程叫做“建链”和“握手”。我将在后面的文章中详细介绍。

除了上面两个点之外，注册MR还有个重要的作用： MR可以避免换页

因为物理内存是有限的，所以操作系统通过换页机制来暂时把某个进程不用的内存内容保存到硬盘中。当该进程需要使用时，再通过缺页中断把硬盘中的内容搬移回内存，这一过程几乎必然导致VA-PA的映射关系发生改变。

由于HCA经常会绕过CPU对用户提供的VA所指向的物理内存区域进行读写，如果前后的VA-PA映射关系发生改变，那么我们在前文提到的VA->PA映射表将失去意义，HCA将无法找到正确的物理地址。

为了防止换页所导致的VA-PA映射关系发生改变，注册MR时会"Pin"住这块内存（亦称“锁页”），即锁定VA-PA的映射关系。也就是说，MR这块内存区域会长期存在于物理内存中不被换页，直到完成通信之后，用户主动注销这片MR。



为了更好的保障安全性，IB协议又提出了Protection Domain（PD）的概念，用于保证RDMA资源间的相互隔离，本文就介绍一下PD的概念。

## PD是什么

PD全称是Protection Domain，意为"保护域"。域的概念我们经常见到，从数学上的“实数域”、“复数域”，到地理上的“空域”、“海域”等等，表示一个空间/范围。在RDMA中，PD像是一个容纳了各种资源（QP、MR等）的“容器”，将这些资源纳入自己的保护范围内，避免他们被未经授权的访问。一个节点中可以定义多个保护域，各个PD所容纳的资源彼此隔离，无法一起使用。

## PD（保护域）的作用

一个用户可能创建多个QP和多个MR，每个QP可能和不同的远端QP建立了连接，比如下图这样（灰色箭头表示QP间的连接关系）：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nU3HCPzcrZU03jDLoyWASgEHggqQfLfAiaR7H8CEmZbBUWVZKibicyhtQNjdXFClcXX7DFS2m3lQibaRQ/640?wx_fmt=png)

由于MR和QP之间并没有绑定关系，这就意味着一旦某个远端的QP与本端的一个QP建立了连接，具备了通信的条件，那么理论上远端节点只要知道VA和R_key（甚至可以靠不断的猜测直到得到一对有效的值），就可以访问本端节点某个MR的内容。

其实一般情况下，MR的虚拟地址VA和秘钥R_Key是很难猜到的，已经可以保证一定的安全性了。但是为了更好的保护内存中的数据，把各种资源的权限做进一步的隔离和划分，我们在又在每个节点中定义了PD，如下图所示：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nU3HCPzcrZU03jDLoyWASgEJ9HlGxEXsf3fLLLWblXpOWTSPmpZysd9QEyPubcSSn1ibna1icY59eyg/640?wx_fmt=png)

图中Node 0上有两个PD，将3个QP和2个MR分为了两组，此外Node 1和Node 2中各有一个PD包含了所有QP和MR。Node 0上的两个PD中的资源不可以一起使用，也就是说QP3和QP9不能访问MR1的数据，QP6也不可以访问MR0的数据。如果我们在数据收发时，指定硬件使用QP3和MR1，那么硬件校验他们不属于同一个PD后，会返回错误。

对于远端节点来说，Node1只能通过QP8相连的QP3来访问Node0的内存，但是因为Node 0的QP3被“圈”到了PD0这个保护域中，所以Node 1的QP8也只能访问MR0对应的内存，无论如何都无法访问MR1中的数据，这是从两个方面限制的：

1. Node 1的QP8只跟Node 0的QP3有连接关系，无法通过Node 0的QP6进行内存访问。
2. Node 0的MR1和QP3属于不同的PD，就算Node 1的QP8拿到了MR1的VA和R_key，硬件也会因为PD不同而拒绝提供服务。

所以就如本文一开始所说的，PD就像是一个容器，将一些RDMA资源保护起来，彼此隔离，以提高安全性。其实RDMA中不止有QP、MR这些资源，后文即将介绍的Address Handle，Memory Window等也是由PD进行隔离保护的。

## 如何使用PD（保护域）

## 还是看上面的图，我们注意到Node 0为了隔离资源，存在两个PD；而Node 1和Node 2只有一个PD包含了所有资源。

我之所以这样画，是为了说明一个节点上划分多少个PD完全是由用户决定的，如果想提高安全性，那么对每个连接到远端节点的QP和供远端访问的MR都应该尽量通过划分PD做到隔离；如果不追求更高的安全性，那么创建一个PD，囊括所有的资源也是可以的。

IB协议中规定：每个节点都至少要有一个PD，每个QP都必须属于一个PD，每个MR也必须属于一个PD。

那么PD的包含关系在软件上是如何体现的呢？它本身是有一个软件实体的（结构体），记录了这个保护域的一些信息。用户在创建QP和MR等资源之前，必须先通过IB框架的接口创建一个PD，拿到它的指针/句柄。接下来在创建QP和MR的时候，需要传入这个PD的指针/句柄，PD信息就会包含在QP和MR中。硬件收发包时，会对QP和MR的PD进行校验。更多的软件协议栈的内容，我会在后面的文章中介绍。

另外需要强调的是，PD（保护域）是本地概念，仅存在于节点内部，对其他节点是不可见的；而MR是对本端和对端都可见的。

**由此可见，通过ibv_reg_mr操作是安全的！**

**灵魂拷问5：有无使用ibv_reg_mr的例子？**

任何rdma测试工具源码中都包含ibv_reg_mr的使用例子，如：rc_pingpong,ib_write_bw。

```
struct ibv_mr *mr_rem_w;uint8_t *buf_rem_w = memalign(page_size, buf_size);if (!buf_rem_w) {fprintf(stderr, "Couldn't allocate work buf.\n");return -1;}//mr_rem_w - MR that allows remote writemr_rem_w = ibv_reg_mr(pd, buf_rem_w, buf_size, IBV_ACCESS_LOCAL_WRITE |IBV_ACCESS_REMOTE_WRITE);//If Remote Write or Remote Atomic is enabled, local Write should be enabled tooif (!mr_rem_w) {fprintf(stderr, "Error, ibv_reg_mr() failed\n");return -1;}
```



**参考链接：**

```
https://docs.nvidia.com/networking/display/rdmacore50/Shared%20Memory%20Regionhttps://community.mellanox.com/s/article/physical-address-memory-regionhttps://www.rdmamojo.com/2012/09/07/ibv_reg_mr/https://zhuanlan.zhihu.com/p/164908617
```

**
**

**16.RDMA中的PCC算法**

本文是一篇学习笔记，参考文献见文后。



PCC的全称是：Programmable Congestion Control，即可编程的拥塞协议。现在主流的智能网卡默认的拥塞协议是DCQCN。关于DCQCN，之前我们已经介绍过很多，我们看看PCC。



第三方的CC算法主要有以下三种：

- Timely (Google)
- Swift (Google)
- HPCC (Alibaba)



上面三种算法中，HPCC我不做介绍。

Timely和Swift都是Google提出的，Swift是在Timely基础上的进一步演进。接下来，本文会介绍几种拥塞算法以及他们的特点。本文在书写过程中参考了网络上的文章，文后给出参考链接。





## 流量控制

流控的原理是，接收方在预测到将要丢包之前通知发送方停止发包。下面介绍几种流控算法的演变。如下图所示，在之前的很多文章中，我都介绍过，Global Pause现在默认都是关闭的。为了解决 Global Pause 不区分流量类型的问题，IEEE 802.1Qbb 定义的 PFC 提出了对网络流量按照优先级 0 - 7 分类，提出了PFC。PFC是有效的防丢包手段，但副作用不小，一般是TOR层交换机和网卡打开，再上层的交换机不会打开PFC。DCQCN是默认的流量控制/拥塞控制标准。



关于关闭Global和PFC的调优，具体内容参考：

[PFC风暴预防](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663511000&idx=1&sn=aafa813f997af9522b3341f8642dc0be&chksm=81d6b4a0b6a13db6df95f5f9c54b0f72998ac6408bdf3eaf16163f32a56183c731a10339f88b&scene=21#wechat_redirect)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmD69683gxNBibUg4W8XY6r0LtIVEAOb9Ry24Q6Qf8rPuWQbmAb8FePevg/640?wx_fmt=png)

  接下来我们看PFC的两种实现：基于PCP的PFC和基于DSCP的PFC。目前生产环境DSCP应用要远比PCP广。



**（1）基于 PCP 的 PFC**

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDU66gZ85dKPyxtk2W7xey97XCWGC7a37Xj8sbicCrFkr37ibJvKGjQxoA/640?wx_fmt=png)

在 IEEE 802.1Qbb 最初的规定，类别 CoS （Class of Service）保存在 L2 层 VLAN Tag 的 PCP（Priority Code Point，3 bits）字段上。也就是说，如果要用PCP需要启用vlan。

**（2）基于 DSCP 的 PFC**

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmD3xDe4174HXTiaLSVicDdEdticQcnSlJj1FjZkE3TfZ98PpKPnKq5oIyeQ/640?wx_fmt=png)

RoCEv2 包含了 IP 头部，可以将优先级保存在 IP 头部的 DSCP 字段。目前大部分厂商的交换机和 RoCE 网卡都已经支持基于 DSCP 的 PFC。



关于PCP和DSCP的设置与切换，详细请参考：

[QoS分类的实践: RoCE的实战系列2](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663509574&idx=1&sn=1abcc2d091b479c9b44c7d0fb68e4c19&chksm=81d6a93eb6a120285035223a3d647f797cb5f4f372562bb122642e123acc223c303cd79a5963&scene=21#wechat_redirect)



**PFC 的问题**

在实际部署中 PFC 性能不佳，会导致不公平问题和 Head-of-Line 堵塞问题。



**拥塞检测**

检测拥塞的方式大致可以归为三类：基于 ECN 的检测和基于 RTT 的检测。





ECN（Explicit Congestion Notification）是 IP 头部 Differentiated Services 字段的后两位，用于指示是否发生了拥塞。它的四种取值的含义如下：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDNSu354h0LcgH2711MhXK7yJJibbOhkibrD42IGEC5HF3O4QglibYeNu0A/640?wx_fmt=png)

00Non ECN-Capable Transport表示发送方不支持 ECN

01ECN Capable Transport表示发送方支持 ECN

10ECN Capable Transport同上

11Congestion Encountered 表示发生了拥塞



部署 ECN 功能一般需要交换机同时开启 RED。如果通信双方都支持 ECN（ECN 为 01 或者 10），当拥塞出现时，交换机会更新报文的 ECN 为 11（Congestion Encountered），再转发给下一跳。接收方可以根据 ECN 标志向发送方汇报拥塞情况，调节发送速率。





RED，即 Random Early Drop，是交换机处理拥塞的一种手段。交换机监控当前的队列深度，当队列接近满了，会开始随机地丢掉一些包。丢弃包的概率与当前队列深度正相关。随机丢弃带来的好处是，对于不同的流显得更公平，发送的包越多，那么被丢弃的概率也越大。

当 RED 和 ECN 同时开启，拥塞发生时交换机不再随机丢包，而是随机为报文设置 ECN。

关于QCQCN的调优，请参考如下文章：

[新-精调RoCE拥塞协议](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663510600&idx=1&sn=857732c873baa4ca8ba769bc743c1f31&chksm=81d6b530b6a13c26e34adcd76ce2badc6001bab896cce0f50cacafc99bcb1668fa1232514862&scene=21#wechat_redirect)

[DCQCN+在RDMA中的应用](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663510276&idx=1&sn=85c53eed3696ca96ddc757f5ec67ffb8&chksm=81d6b67cb6a13f6afdf61e39ab81679a16dbafe9a0ff4371ac3bc16c454de7eb7a7ceda20645&scene=21#wechat_redirect)



Google提出的Timely和Swift都是基于RTT进行检测的，接下来我们看RTT。

（3）基于 RTT 检测

RTT（Round-Trip Time）是发送方将数据包发送出去，到接收到对端的确认包之间的时间间隔。RTT 能够反映端到端的网络延迟，如果发生拥塞，数据包会在接收队列中排队等待，RTT 也会相应较高。而 ECN 只能够反映超过队列阈值的包数量，无法精确量化延迟。

RTT 可以选择在软件层或者硬件层做统计。一般网卡接收到数据包后，通过中断通知上层，由操作系统调度中断处理收包事件。中断和调度都将引入一些误差。因此，更精确地统计最好由硬件完成，当网卡接收到包时，网卡立即回复一个 ACK 包，发送方可以根据它的到达时间计算 RTT。

需要注意的是，ACK 回复包如果受到其他流量影响遇到拥塞，那么 RTT 计算会有偏差。可以为 ACK 回复包设置更高优先级。或者保证收发两端网卡的时钟基本上同步，然后在回复包加上时间戳信息。另外，网络路径的切换也会带来一些延迟的变化。

下面介绍 RDMA 下分别基于 ECN 和 RTT 检测的两种主流控制算法。



**控制算法**

DCQCN 可以划分为三个部分：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDMibAYnR2axC4tbSzoGKdDbUHQT3HfGQWeGEM24qkd4ldP6P5Gql8EIw/640?wx_fmt=png)

*拥塞点算法*

中间交换机检查当前拥塞情况，当队列深度超过阈值时，通过 RED/ECN 标记报文，然后转发给下一跳。



*通知点算法*

由接收方网卡完成，主要是把拥塞信息通知到发送方。RoCEv2 新增了 CNP（Congestion Notification Packets）控制报文用于拥塞通知。接收方网卡检查每个接收包的 ECN 标志，如果 CN 被设置，那么发送 CNP 给发送方。为了减少性能开销，每 50 us 只发送一个 CNP（DCTCP 是每个包都回复一个）。

*响应点算法*

由发送方网卡完成，负责调节发送速率避免拥塞。在每个周期窗口，发送方网卡更新拥塞程度参数（取值为 0 ~ 1），更新的依据是：

●	如果收到拥塞通知，增加拥塞参数

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDsPO5ojNkDoSQ9PAYWWkChoOZK0Kn7Z4ibibVDTBBR1EpUSicWX8XWnHiaQ/640?wx_fmt=png)

​	否则，逐渐减少拥塞参数

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDhVHFsHTcV4o3WFiajWGv6DvmIo97zULLO1WpygkNXyYCOMWd2AuFfjg/640?wx_fmt=png)

然后根据拥塞程度参数调节发送速率（Rt 为目标速率，Rc 为当前速率），

●	如果收到拥塞通知，降低速率（最多降低到原来的一半）：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmD1Lrx2ibKqEHRfUbBkJgSKxthCD7m4e72acTE2pPyBiaiaoazQHXsSTJ7g/640?wx_fmt=png)

●	否则（与 QCN 一样） ○	快速恢复（持续没收到拥塞通知的前五个周期，每个周期为每发出 150 KB 报文或者 10 ms），向上一次遇到拥塞的速率 Rt 靠近

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmD67PiaqVqh9pTRIk7l97QkguackD5DVMOiaz4vFAasQK3LT5medNcLS9Q/640?wx_fmt=png)

○	主动恢复（快速恢复后，每个周期为 50 个报文或者 5 ms），探测可用带宽（可能超过 Rt）：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmD9iahTQia0v33XpZTezwr1qHibBtcSPzyzy4PQXW3WV0jPLb1rmap8ibWCg/640?wx_fmt=png)

其中拥塞点算法依赖于交换机的已有的 RED/ECN 功能。而通知点和响应点算法需要在 RDMA 网卡实现，包括收发 CNP 报文、发送端需要增加对于每个 Flow 的计时器和字节计数器。目前 Mellanox 的网卡已经支持 DCQCN。



**Timely（RTT 检测）**

Timely 是它是数据中心网络第一个基于延迟的拥塞控制算法。

Timely 算法主要包括三个部分，它们都运行在发送方。算法不涉及中间交换机的处理，但要求接收方网卡对于每一个接收包回复一个 ACK。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDvvSUfCJJTqxO3RyJcIb4cEaCvgSFfic9SOUTfsSPOMlfbT3ENVGWOWQ/640?wx_fmt=png)

*RTT 统计模块*

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDqs0vxOn5KeFB1n5QpYgAKa0FszYaiaAZKBd5yrFhYJS4VPCXuHc3Gicw/640?wx_fmt=png)

Timely 中将 RTT 定义为数据包在网络中传播时间与在队列中等待时间之和。下面的公式中，发送的时间戳由发送方软件层记录；完成的时间戳为发送方接收到接收方网卡返回的 ACK 时间戳。由于一个大包可能被拆分成多个，同时数据包从网卡发送出去有传输时延，因此还需要减去这部分时间。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDTncZpjRjpDxDiajvc3kLfGtfNkIAlDibBXIYDAQ7lxYzTxHdZNOXaLyw/640?wx_fmt=png)

*速率计算模块*

对于每一个发包结束事件，速率计算模块从 RTT 统计模块得到该包的 RTT，然后输出一个期望的发送速率。

Timely 并没有根据 RTT 的绝对值来衡量拥塞情况，而是通过 RTT 的梯度变化来捕捉延迟变化：当 RTT 上升时，表明拥塞愈发严重；反之，拥塞正在减轻。这种方式对于延迟更加敏感，有利于满足应用低延迟需求。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDwN7GibpkZob4QhFLdmHGuBsIMFSrLe2mXvgFfXyrPibDSxiacYPI2wTAg/640?wx_fmt=png)

速率计算的算法如上图，首先计算 RTT 梯度变化。计算连续两个 RTT 的差值，并与历史值做平滑化过滤掉突发抖动带来的偏差，然后再与 minimum RTT（可以取值为估计的网络传播往返时间）做归一化，得到 RTT 梯度变化率。然后确定期望的发送速率：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDcVAua1tAgsrhGSkFffl6zBfckPnUXKDXzhZcFibqBV3IWRDayWwuYrQ/640?wx_fmt=png)



●	如果新的 RTT 低于 Tlow，那么采用和性增长（Additive Increment）探测可用带宽，提高发送速率。流量刚启动时，RTT 可能会突然增长，这时候不应该视为拥塞加重。

●	如果新的 RTT 高于 Thigh，那么采用乘性减少（Multiplicative Decrement）减少发送速率。如果 RTT 持续维持在高水平，但梯度几乎没有变化，就需要这个机制防止拥塞。

●	根据 RTT 梯度变化率计算，

○	如果 RTT 梯度变化率不为正，说明拥塞减轻，那么通过和性增长提高发送速率。如果连续五次 RTT 梯度变化率都不为正，那么增长步长相应提高。

○	如果 RTT 梯度变化率为正，说明拥塞加重，那么通过乘性减少方式降低发送速率。

*速率控制模块*

Timely 在软件层增加了一个调度器。当应用需要发送数据包时，不会将发送请求提交给网卡，而是先交给调度器。根据前一模块得到的期望发送速率，调度器将注入发包延迟，把能够放行的数据包交给网卡发送，将需要延迟发送的数据包加入等待队列中，在未来发送。

##  

## 算法对比

DCQCN 作者随后于 2016 年在文章 [6] 中，通过流体模型和仿真测试证明 Timely 将 RTT 作为唯一衡量标准，难以同时兼顾公平性和延迟上限；而 DCQCN 却可以做到。感兴趣的同学可以了解一下。

下面从检测方式、不同通信组件行为、速率调整方式、适用场景等角度对比 DCQCN 和 Timely 两种拥塞控制算法，同时也把经典的 TCP Tahoe 流控作为参考。DCQCN 和 Timely 没有采用基于窗口的调整方式，主要是窗口方式可能出现突发的流量带来较大延迟，同时实现起来也比基于速率的方式复杂。



| 检测方式     | ECN                                                          | RTT 的梯度变化                  |
| ------------ | ------------------------------------------------------------ | ------------------------------- |
| 交换机       | 检测拥塞设置 ECN                                             | 无                              |
| 接收方       | 网卡发送 CNP 通知拥塞                                        | 网卡发送 ACK                    |
| 发送方       | 网卡根据是否有 CNP 调整发送速率                              | 软件调度器根据 RTT 调整发送速率 |
| 速率调整方式 | 基于拥塞参数调节，增加时包括快速增加和主动增加两阶段，减少时是乘性减 | 基于 RTT 的 AIMD                |
| 适用场景     | RoCEv2                                                       | 通用，只要网卡支持发送 ACK      |



**备注：AIMD：**和性增长/乘性降低（英语：additive-increase/multiplicative-decrease、AIMD）算法是一个反馈控制算法，最广为人知的用途是在TCP拥塞控制。AIMD将拥塞窗口的线性增长与监测到拥塞时的指数降低相结合。使用AIMD拥塞控制的多个流将最终收敛到使用等量的共享链路[1]。乘性增长/乘性降低（MIMD）和加性增长/加性降低（AIAD）的相关方案无法达到稳定。

既然RTT的通用性更强，那么为何此前默认的CC协议是DCQCN而不是RTT？

数据中心RTTs很难以微秒级的粒度进行测量。这种精度水平很容易被主机延迟所淹没，如确认的中断处理。. 但是现在的智能网卡这个功能比较完善了.

**Swift (Google)**

Swift的设计比TIMELY简化了，因为它发现使用一个绝对的目标延迟是高性能和稳健的。第二，对结构和主机的拥堵做出反应很重要。我们最初低估了主机的拥堵（就像大多数设计一样），但这两种形式在一系列对延迟敏感、IOPS密集和字节密集的工作负载中都很重要。为此，延迟很容易被分解。第三，我们必须支持广泛的流量模式，包括大规模传输。这个范围导致我们在有更多的流量超过路径的带宽-延迟乘积（BDP）时对数据包进行定位，同时在更高的流速下使用一个窗口以提高CPU效率。



TIMELY指出，RTT可以用现代硬件精确测量，而且它提供了一个多比特拥堵信号，即它编码了拥堵的程度，而不仅仅是它的存在。Swift进一步分解了端到端RTT，将结构和主机问题分开；通过结合网卡硬件的时间戳和Pony Express等基于轮询的传输方式，使延迟测量更加精确。



Swift的核心是区分 fabric congestion 和 endpoint congestion。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDSmIqOmufBzwicPuIXw6HLlgOq2Kx1Gvv7H5qzgzZhp2KJaysO8v2VZw/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDlsXUJVsXJ5V6Q2XuKShibTCXZh9RqmmjykMM3n7YFop5ggbGsE6uKmQ/640?wx_fmt=png)

fcwnd是fabric delay，具体而言是fabric target delay；ecwnd是endpoint delay。最终在两个数值中去小值作为拥塞窗口。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmD7W7dSftGMiaeUVATyVGV8UdiceuGUzJThpYS1ia6PGicFMgcMchZSam8gw/640?wx_fmt=png)

那么，如何确定 fabirc target delay？我们查看下面列出的公式：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDDHKXc1PG4INwDia4nVxwVydBTnvGyyTprRLqqe5wqRPyRKEKa3zhT5Q/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXrRYk1sia7BJCBTM1oiaJLmDIeJmWMzDoLIlXNm847Bvs5Ugy2CmsUtlOfQtD2srICNwhH2ibkcz7nA/640?wx_fmt=png)



NVIDIA Mellanox的SmartNic从CX6 DX开始支持PCC。由于篇幅有限，后面文章会介绍算法切换的方法。









参考文献：

https://cloud.tencent.com/developer/news/699345

https://yi-ran.github.io/2020/08/06/Swift-SIGCOMM-2020/



**
**

**17.精调RoCE拥塞协议**

**QoS与拥塞协议全图**

无论是阻塞协议还是QoS协议，其最终目的都是不发生丢包或者让丢包造成的影响最小。在生产上DCQCN默认都是开启。通过优化参数，目的是不触发PFC。


我们查看协议汇总全图：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW8hlObicE0gZ6guktVq6V2hxJ6TXS72GoBwuJf10KiaHAwCZUaxsRqQEO7NUlANh66qwibEKFf7827Q/640?wx_fmt=png)



经过一些实验证明：DCQCN调速参数比ECN对TX-PFC触发数量影响更大。在某一个固定DCQCN参数下，通过调整ECN参数，可以提升吞吐量，降低PFC。



下面我们先看看这几个参数的介绍和调整。



**什么是WRED？**

RED（Random Early Discard）技术，其思想是通过监测路由器端口平均队列长度来探测拥塞，一旦发现拥塞出现，就随机选择连接来通知，使这些连接的发送端在队列缓冲区溢出前减小发送窗口，降低数据发送速率，从而缓解网络拥塞。这种技术优势体现在“随机”上，即网络出现拥塞早期征兆时，先以概率p随机丢弃个别连接的分组，让拥塞控制只在某些TCP连接上进行，避免发生全局性拥塞控制。



加权随机先期检测（WRED：Weighted Random Early Detection）是将随机先期检测与优先级排队结合起来，这种结合为高优先级分组提供了优先通信处理能力。当某个接口开始出现拥塞时，它有选择地丢弃较低优先级的通信，而不是简单地随机丢弃分组。



ECN和DCQCN之前文章已经介绍很多了，这里不再赘述。对概念印象不深的话，可以参考：

[大规模RDMA的拥塞协议-DCQCN](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663509454&idx=1&sn=f3af4a3dfdb8145d08ea4d442d13318d&chksm=81d6aab6b6a123a08069978bc5279349111d7ad3bcc8500bfd9958e1c6dd2cb9baa397160df0&scene=21#wechat_redirect)



对于有损网络，如果不启用ECN（那么DCQCN也就无法生效），则强烈建议启用WRED，以加强网络对拥堵的反应，并尽量避免尾部掉线。



那么，WRED、ECN、DCQCN三个参数怎么设置？



关于WRED和ECN，我们来看网卡的两个寄存器。

- **CWTP: Congestion WRED ECN TClass Profile Register**
- CWTPM：Congestion WRED ECN TClass and Pool Mapping Register



首先确认卡的Port：

\# show_gids

```
DEV     PORT    INDEX   GID                                     IPv4            VER     DEV---     ----    -----   ---                                     ------------    ---     ---mlx5_1  1       0       fe80:0000:0000:0000:0e42:a1ff:fe2d:9c3b                 v1      enp4s0f1mlx5_1  1       1       fe80:0000:0000:0000:0e42:a1ff:fe2d:9c3b                 v2      enp4s0f1n_gids_found=2
```

查看网卡tc和priority的关系：

```
[root@l-csi-0835d ~]# mlnx_qos -i enp4s0f1DCBX mode: OS controlledPriority trust state: pcpdefault priority:Receive buffer size (bytes): 0,156096,0,0,0,0,0,0,Cable len: 7PFC configuration:priority    0   1   2   3   4   5   6   7enabled     0   0   0   0   0   0   0   0buffer      1   1   1   1   1   1   1   1tc: 1 ratelimit: unlimited, tsa: vendorpriority:  0tc: 0 ratelimit: unlimited, tsa: vendorpriority:  1tc: 2 ratelimit: unlimited, tsa: vendorpriority:  2tc: 3 ratelimit: unlimited, tsa: vendorpriority:  3tc: 4 ratelimit: unlimited, tsa: vendorpriority:  4tc: 5 ratelimit: unlimited, tsa: vendorpriority:  5tc: 6 ratelimit: unlimited, tsa: vendorpriority:  6tc: 7 ratelimit: unlimited, tsa: vendorpriority:  7
```

接下来，我们针对0000:04:00.0卡的port 0、tc5分别查看CWTP和CWTPM寄存器。



**CWTP参数**

CWTP查看结果如下，我们关注如下参数设置：mode,profile1_min,profile1_max,profile1_percent，profile2_min,profile2_max,profile2_percent,profile3_min,profile3_max,profile3_percent

```
#  mlxreg -d 0000:04:00.0  --reg_name CWTP --get  --indexes "local_port=0,pnat=2,traffic_class=5"Sending access register...Field Name          | Data=================================pnat                | 0x00000002local_port          | 0x00000000traffic_class       | 0x00000005mode                | 0x00000000profile1_min        | 0x00000040profile1_max        | 0x000038c0profile1_percent    | 0x00000000profile2_min        | 0x00000040profile2_max        | 0x000038c0profile2_percent    | 0x00000000profile3_min        | 0x00000040profile3_max        | 0x000038c0profile3_percent    | 0x00000000=================================
```

mode参数，即定义WRED和ECN的阈值模式。

0: 固定

1: 百分比



profile_min:

最小平均队列大小。





profile_percent

最大平均队列规模的WRED和ECN标记的百分比。





profile_max

当mode数值为1 最大平均队列规模。



上面参数设置范例：

```
mlxreg -d 0000:01:00.0 --set "mode=0,profile1_min=0x2c0,profile1_max=0x1e40,profile1_percent=30,profile2_min=0x40,profile2_max=0x38c0,profile2_percent=0,profile3_min=0x40,profile3_max=0x38c0,profile3_percent=0" -y --reg_name CWTP --indexes "local_port=0,pnat=2,traffic_class=5"
```



**CWTPM参数**

关于CWTPM，我们关注ee和ew 两个参数。

```
#  mlxreg -d CWTPM0000:04:00.0  --reg_name CWTPM --get  --indexes "local_port=0,pnat=2,traffic_class=5"Sending access register...Field Name       | Data==============================pnat             | 0x00000002local_port       | 0x00000000traffic_class    | 0x00000005ee               | 0x00000000ew               | 0x00000000==============================
```



ee：在指定的TC打开或者关闭ECN

Enable ECN on traffic class

0: Disable

1: Enable



ew：在指定的TC打开或关闭WRED

0: Disable

1: Enable



上面参数设置范例：

```
mlxreg -d 0000:01:00.0 -y --set "ee=1,ew=0" --reg_name CWTPM --indexes "local_port=0,pnat=2,traffic_class=5"
```



若要转换数值，可以使用在线转换工具：https://www.sojson.com/hexconvert/16to10.html



**DCQCN参数**

**发送端：**

/sys/class/net/device_name/ecn/roce_rp/rate_reduce_monitor_period

单位是µS

**接收端：**

/sys/class/net/device_name/ecn/roce_np/min_time_between_cnps

单位是µS

```
# pwd/sys/class/net/enp4s0f0/ecn# lsroce_np  roce_rp# cat roce_np/min_time_between_cnps4# cat roce_rp/rate_reduce_monitor_period4
```





**参数参考**

在大规模的压力测试环境下，如QP>1000,出于提升吞吐量、降低PFC的目的，以下参数设置供参考：

当DCQCN参数rate_reduce_monitor_period/min_time_between_cnps=2时，以及WRED和ECN的**CWTP**参数如下时：

 mode=0,profile1_min=0x380,profile1_max=0x2740,profile1_percent=20,profile2_min=0x380,profile2_max=0x2740,profile2_percent=20,profile3_min=0x380,profile3_max=0x2740,profile3_percent=20

我们看到上面三个profile是相同的。



设置方法：

```
echo 2 > /sys/class/net/eth0/ecn/roce_rp/rate_reduce_monitor_periodecho 2 >  /sys/class/net/eth0/ecn/roce_np/min_time_between_cnps
mlxreg -d 0000:01:00.0 --set "mode=0,profile1_min=0x380,profile1_max=0x2740,profile1_percent=20,profile2_min=0x380,profile2_max=0x2740,profile2_percent=20,profile3_min=0x380,profile3_max=0x2740,profile3_percent=20" -y --reg_name CWTP --indexes "local_port=0,pnat=2,traffic_class=5"
```



DCQCP除了上述比较基本的参数外，还有更为细致的参数设置，在对应网卡的路径下。但这些参数一般不需要特别调整，是用作debug的。



\#cd /sys/kernel/debug/mlx5/0000:31:00.1/cc_params

```
-rw-------  1 root root 0 Jan 18 08:22 np_cnp_dscp-rw-------  1 root root 0 Jan 18 08:22 np_cnp_prio-rw-------  1 root root 0 Jan 18 08:22 np_cnp_prio_mode-rw-------  1 root root 0 Jan 18 08:22 np_min_time_between_cnps-rw-------  1 root root 0 Jan 18 08:22 rp_ai_rate-rw-------  1 root root 0 Jan 18 08:22 rp_byte_reset-rw-------  1 root root 0 Jan 18 08:22 rp_clamp_tgt_rate-rw-------  1 root root 0 Jan 18 08:22 rp_clamp_tgt_rate_ati-rw-------  1 root root 0 Jan 18 08:22 rp_dce_tcp_g-rw-------  1 root root 0 Jan 18 08:22 rp_dce_tcp_rtt-rw-------  1 root root 0 Jan 18 08:22 rp_gd-rw-------  1 root root 0 Jan 18 08:22 rp_hai_rate-rw-------  1 root root 0 Jan 18 08:22 rp_initial_alpha_value-rw-------  1 root root 0 Jan 18 08:22 rp_max_rate-rw-------  1 root root 0 Jan 18 08:22 rp_min_dec_fac-rw-------  1 root root 0 Jan 18 08:22 rp_min_rate-rw-------  1 root root 0 Jan 18 08:22 rp_rate_reduce_monitor_period-rw-------  1 root root 0 Jan 18 08:22 rp_rate_to_set_on_first_cnp-rw-------  1 root root 0 Jan 18 08:22 rp_threshold-rw-------  1 root root 0 Jan 18 08:22 rp_time_reset
```

https://patchwork.kernel.org/project/linux-rdma/patch/20170530070515.6836-1-leon@kernel.org/



接下来，我们看一下各个参数的大致解释：

```
rp_clamp_tgt_rate    When set target rate is updated to  current rate                          rp_clamp_tgt_rate_ati        When set update target rate based on timer as well                         rp_time_reset          time between rate increase if no  CNP is received unit in usec           rp_byte_reset    Number of bytes between rate inease if no CNP is received                   rp_threshold          Threshold for reaction point rate   control                            rp_ai_rate                    Rate for target rate, unit in Mbps    rp_hai_rate                   Rate for hyper increase state unit in Mbps         rp_min_dec_fac         Minimum factor by which the current  transmit rate can be changed when  processing a CNP, unit is percerntage rp_min_rate                Minimum value for rate limit,  unit in Mbps                    rp_rate_to_set_on_first_cnp    Rate that is set when first CNP is   received, unit is Mbps              rp_dce_tcp_g               Used to calculate alpha               rp_dce_tcp_rtt              Time between updates of alpha value,  unit is usec                            rp_rate_reduce_monitor_period  Minimum time between consecutive rate reductions                         rp_initial_alpha_value    Initial value of alpha            rp_gd                        When CNP is received, flow rate is  reduced based on gd, rp_gd is given as  log2(rp_gd)                      np_cnp_dscp                  dscp code point for generated cnp     np_cnp_prio_mode               802.1p priority for generated cnp     np_cnp_prio                    cnp priority mode
```







**18.从Driver源码分析RDMA问题**

**问题环境：**

两台服务器，安装Debian操作系统，使用NVIDIA Mellanox CX-6 DX双口网卡（默认开启RoCE模式）。



每台服务器网卡的两个网口配置Bond，然后基于Bond设备配置VF，即VF LAG。PF配置Switchdev模式。然后配置Overlay。



**问题现象：**

从一台服务器使用ib_write_bw从VF对另外一台服务器的的VF发压力，指定100个qp，通过抓包分析，发现QP的Src Port相同。



注：下面文件抓包是VF给VM使用，然后在host中抓包。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyrqpqtVt1ibSUaxNHMK1VRC6qNmoIwHcFV0aaNNyQEic4fymPian2nvTibSw/640?wx_fmt=png)



VF LAG策略是HW Hash，依据五元组去选physical port。因此如果多qp相同的Src port会造成流量会只走一个PF，吞吐量无法发挥bond的效果和优势。  



需要注意的是，如果Overlay的情况，那么抓到的网络包，会有内外两层。内层是overlay、外层是underlay。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyrlysIWhtEgPhEJI6XhgD2PzbRjicfDBrdLxU9NlZqIw8FD0mjIKibvVibw/640?wx_fmt=png)

针对这个问题，针对多个QP，内（6111）外（49152）两层的Src port都是相同的。这里我们关注内层，就是roce的source port。





尝试在实验环境复现此问题（相同的OFED、FW、Linux版本以及相同的bond配置），没有成功。多qp的src port均不同。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyr5v77vibSka7JApMh0ANCfvaNDPDQQt7H44ia7hCibyuhACcia9K4IHEwNQ/640?wx_fmt=png)



**查看驱动源码**

QP建连时候src port的设定方式，我们查看驱动源码中的实现逻辑：

/usr/src/mlnx-ofed-kernel-5.4/drivers/infiniband/hw/mlx5/qp.c

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyribGUjKKiaUl85u9HyVZwuQfq3rUsUYSiabKLWkoKBL41KOk3FrFfJqXHA/640?wx_fmt=png)

为了验证驱动实现是否正确，我们分别强制指定src port合法值和非法值，看驱动是否可以将src port的指定值传导下去。



增加测试代码，在代码中强制设置一个src port，即49152，也就是之前不变的src port数值。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyrv2dpaoonpdZG0TT8MTSbY0JUrknU9Qpg16qDD8Qr9vDUQMwFNFNPng/640?wx_fmt=png)

root@l-csi-r750-04:/usr/src/mlnx-ofed-kernel-5.4/# ./configure

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyre03J5cWISLQwYjnsRRfQTlFDSH1W4yMmmvKJA0xsZibwsrPzayIzSZA/640?wx_fmt=png)

root@l-csi-r750-04:/usr/src/mlnx-ofed-kernel-5.4/#./make -j8

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyribAOqkMhYyiagRaQ5frib6dxg8MkqWz6rW0F7Snk5ibwG29K8fnYDhPTqA/640?wx_fmt=png)

root@l-csi-r750-04:/usr/src/mlnx-ofed-kernel-5.4/#./make install

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyrNws7bBtzQmoIqJk4e7BIcia5mOWecTvmuw4KHibksghIDiaCkIZwBic1hg/640?wx_fmt=png)

驱动编译成功以后：

1. 需要重新操作此前对网卡的相关配置（例如配置VF、配置DSCP等等）
2. 重启服务/etc/init.d/openibd restart



压力测试后，查看日志，如下图所示。说明驱动可以把设置的和合法值写下去：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyrU9SIuh9OrGwUr7uu98H5oOq8oIsEiagkxOINpXZV3oBPXniaZGVaYOLA/640?wx_fmt=png)

再次修改代码，将src port设置为一个非法值:

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyrliaXCS3H1V0MH6V7eicr05ngNEAniciceNTEJC7pultC7b9hFdZvoibZ0zg/640?wx_fmt=png)

编译后进行压力测试，报错：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyrmM6KeicWoBQ5WpGrXJDbGFCmoA9uRhANc1BHBznuDKuDVM7tIMgwXjA/640?wx_fmt=png)

将代码中设置src port的逻辑注释掉：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyrO2qqiaPFsH0ic9KfTbYupoxw6pMCpvIQdNpVtQhUq85h9ABjXFtZb8lA/640?wx_fmt=png)

重新编译驱动，发压力测试，依然会出现问题：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyrRmEnlCcUu4HemtFYErFicutqte4g6OQlP4GVAE72BKdicX0aaflzmyvA/640?wx_fmt=png)

也就是说，针对代码中设置的数值，驱动都会传到下去，但对于传递的非法值，发压力的时候会报错。



由此可见，默认代码的逻辑是不指定src port，我们验证了驱动可以传到代码中书写的设置逻辑，因此出现src port相同的情况，不是OFED驱动造成的。



既然不是OFED驱动造成的，是否可能是由其他地方覆盖过来的呢？如FW。但我们在实验环境使用相同版本的FW，并未复现问题，因此这个问题引入不是FW。那么是否可能是由inbox driver引入的呢？



**问题确认**

查看inbox驱动的代码逻辑，设置udp_port并未考虑需要做hash的场景：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXwNrgnQAG0Ykkr2vdPNDyrFcMqzpa5h4u1piaCVIy3v7V6NzZsf0CCEicYPTBJFjW4RQyict0gWvuRA/640?wx_fmt=png)

也就是说，如果使用inbox driver，那么无论起多少个QP，起src port都取上图代码中的固定值，即49152。



因此，通过判断，发现问题的引入是没有完整安装OFED驱动，引入了inbox driver所致。



**19.六板斧-有损RDMA网络**

在RoCEv2网络中，我们理想是配置无损网络。但无损网络要求网卡和交换机都配置PFC。PFC的逻辑在于如何不丢包，但PFC会有一些副作用。



有损网络则是允许丢包，所以有损网络的技术，都是网络出现丢包以后怎么处理、尽量减少丢包的逻辑。



有损网络是CX-5引入的，包括的功能有：针对丢包快速响应、每个QP的传输窗口、慢启动、自适应重传。CX-6又引入了新功能：选择性重复、可编程拥塞协议、



有损网络六板斧如下，这些技术都是在丢包情况出现后，如何避免进一步丢包的止损招数。：

- ·    丢包快速响应-慢重启

- ·    从idle慢启动

- ·    设定每个qp的传输窗口

- ·    自适应重传

- ​     选择性重传

- ·    adaptive timer（含义后面介绍）

  





参照以上六点，我们在系统里查看一个网卡的参数（我是在CX 5环境下查看的）：

```
#  lspci | grep Mell5e:00.0 Ethernet controller: Mellanox Technologies MT28800 Family [ConnectX-5 Ex]5e:00.1 Ethernet controller: Mellanox Technologies MT28800 Family [ConnectX-5 Ex][root@l-csi-c6420d-03 mst]# mlxreg -d 5e:00.0 --reg_name ROCE_ACCL --getSending access register...Field Name                             | Data====================================================roce_adp_retrans_field_select          | 0x00000001roce_tx_window_field_select            | 0x00000001roce_slow_restart_field_select         | 0x00000001roce_slow_restart_idle_field_select    | 0x00000001roce_adp_retrans_en                    | 0x00000001roce_tx_window_en                      | 0x00000000roce_slow_restart_en                   | 0x00000001roce_slow_restart_idle_en              | 0x00000000====================================================
```



将六板斧和上述参数对应起来：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWlYlCyzk2IibPIesAIFmj5Xibd8ssfHhdK4thkSfr2Eh5scnveJe3SgY6MHsuficsibIzWK4T3bY2WXQ/640?wx_fmt=png)

五板斧中的adaptive timer，是由硬件控制的，无需参数侧设置。因此上表中没有这个设置。adaptive timer的原理是：从一个小的超时值开始，如果没有掉线，减少超时值，直到最小值，如果出现掉线，增加超时值，直到最大值，ack-timer的目标值是接近RTT



***\*整体上看，对于lossy\**\**，transition windows\**\**和adaptive timer效果比较明显\**\**。\****



下面考虑几个问题。

1. 在有损网络下，当接收端有一个包没收到的时候，会向接收端发什么

接收端向发送端发送两个包：oos_nack、cnp（ECN标记产生的，让发送端降速）。



2. 接收端什么时候向发送端发ack?

- 报文传完
- OOS（产生的原因是：收到两个psn，号不对）



3.关于重传机制

- ConnectX-4：从一个IB重传协议的丢失段重复传输，go-back-N。这可能会造成大量包重传
- ConnectX-5及以上。通过使用硬件重传来改善对丢包的反应
- ConnectX-6 Dx。使用一个专有的选择性重复协议



3.在有损网络中，什么时候重传？

- 当接收端收到out-of-syquence（乱序）nack,重传。
-  最后一个报文丢包
-  Ack自己丢了
-  OOS nack丢包

 

后三种情况，需要依赖timer过期来重传。如果等timer过期，需要等很久，会增加延迟。adaptive timer原理是不用静态的timer过期，硬件自己来管。自己猜测，timer timeout自适应调小，来适应过期的时间。



 对于静态timer下，简单判断是：如果包重传的有点多，那就是timer out太小。如果丢包，那就是timer超时设置的太大。





关于有损网络参数设置方法，也很简单，我们以修改一个参数为例：

```
#  mlxreg -d 5e:00.1 --reg_name ROCE_ACCL --getSending access register...Field Name                             | Data====================================================roce_adp_retrans_field_select          | 0x00000001roce_tx_window_field_select            | 0x00000001roce_slow_restart_field_select         | 0x00000001roce_slow_restart_idle_field_select    | 0x00000001roce_adp_retrans_en                    | 0x00000001roce_tx_window_en                      | 0x00000000roce_slow_restart_en                   | 0x00000001roce_slow_restart_idle_en              | 0x00000000====================================================[root@l-csi-c6420d-03 ~]#  mlxreg -d 5e:00.1 --reg_name ROCE_ACCL --set roce_slow_restart_idle_en=0x01You are about to send access register: ROCE_ACCL with the following data:Field Name                             | Data====================================================roce_adp_retrans_field_select          | 0x00000001roce_tx_window_field_select            | 0x00000001roce_slow_restart_field_select         | 0x00000001roce_slow_restart_idle_field_select    | 0x00000001roce_adp_retrans_en                    | 0x00000001roce_tx_window_en                      | 0x00000000roce_slow_restart_en                   | 0x00000001roce_slow_restart_idle_en              | 0x00000001==================================================== Do you want to continue ? (y/n) [n] : y Sending access register...[root@l-csi-c6420d-03 ~]#  mlxreg -d 5e:00.1 --reg_name ROCE_ACCL --getSending access register...Field Name                             | Data====================================================roce_adp_retrans_field_select          | 0x00000001roce_tx_window_field_select            | 0x00000001roce_slow_restart_field_select         | 0x00000001roce_slow_restart_idle_field_select    | 0x00000001roce_adp_retrans_en                    | 0x00000001roce_tx_window_en                      | 0x00000000roce_slow_restart_en                   | 0x00000001roce_slow_restart_idle_en              | 0x00000001====================================================
```



关于选择性重传的设置

```
#mlxconfig -d <dev> set RDMA_SELECTIVE_REPEAT_EN=0x1
```







https://community.mellanox.com/s/article/How-to-Enable-Disable-Lossy-RoCE-Accelerations



**20.RDMA性能调优与故障诊断思路**

[RDMA性能调优与故障诊断思路](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663510300&idx=1&sn=34df88dc6e55c32d0e2db4fcb23eac0a&chksm=81d6b664b6a13f72f9fae392e10d9e41e2d043cf1362723fe6a49a5d7d510f51f14ca7bb4dfb&scene=21#wechat_redirect)



**21.DCQCN+在RDMA中的应用**

本文是下图两篇论文的读书笔记。在书写笔记时，我对论文原文做了适当的精简。文中**加粗红字**是我的一些理解。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1cgXBsAhPYGG00zxknaFBpLHkXibq5dBCzedIB09ZiaA7no2bW5icIuwTw/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVGicCdG2yloB8qwdPMuhWia0cfe5XLg2EajtS0Hnrf9ibG0RRMxkk6FKWOz4JX8yWE21sIe1kv4Oktg/640?wx_fmt=png)



**一、ECN与CNP的详细搭配使用**



如果支持RoCEv2拥塞管理，在收到IP.ECN字段为'11'的有效RoCEv2数据包时，HCA应生成一个RoCEv2 CNP，指向收到数据包的来源。HCA可以选择为给定QP上的多个此类ECN标记的数据包发送一个CNP，也就是没必要一个带有ECN的数据包就回一个CNP。



 RoCEv2 CNP Packet format 如下：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVGicCdG2yloB8qwdPMuhWia0nyOw1kcquDYm5lajYUhlcQvwVde5YtnOEnDVfb7qcFtaicqlkz29MXg/640?wx_fmt=png)

每个字段的含义如下：



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVGicCdG2yloB8qwdPMuhWia08AEPiaMdibCoKHAkE8aLcC1X5IHxX3RwG3uZeaU3G5wxxlxAudM0h8Zw/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVGicCdG2yloB8qwdPMuhWia0Xs42qcbKdwzfhraN6KxNiaqF3w8xvZLP8waia0rkcBtzKRpewicq8rqTg/640?wx_fmt=png)

二、 DCQCN的机制是什么？

DQCN 是一种基于速率的端到端拥塞协议，它建立在 QCN 和 DCTCP 之上。大多数 DCQCN 功能在 NIC 中实现。**DCQCN和RoCE v2是绝配，DCQCN是RoCE v2的专供****。DCQCN仅****要求交换机支持RED和ECN技术。DCQCN是一种基于速率的拥塞控制方案。**





如前所述，我们对 DCQCN 有三个核心要求：

(i) 在无损、L3 路由、数据中心网络上运行的能力，

(ii) 低 CPU 开销和

(iii) 在无拥塞的常见情况下超快速启动。



此外，我们还希望 DCQCN 为公平的带宽分配提供快速收敛，避免稳定点附近的振荡，保持低队列长度，并确保高链路利用率。



还有一些实际问题：我们不能要求交换机提供任何自定义功能，而且由于协议是在 NIC 中实现的，我们必须注意实现开销和复杂性。



DCQCN 算法由发送方（反应点RP）、交换机（拥塞点CP）和接收方（通知点NP）组成。



**接下来，我们看RP（发送者）、CP（拥塞点）、NP（接收方）这三个子算法的实现。**

**算法**

- CP**（拥塞点）** 算法：CP 算法与 DCTCP 相同**（DCTCP用到了显示拥塞协议ECN）**。在出口队列中（**PFC-交换机入口拥塞管理机制、ECN-交换机出口拥塞控制机制**），如果队列长度超过阈值，则到达的数据包会被 ECN标记。这是使用所有现代交换机支持的 RED功能完成的。为了模拟 DCTCP，我们可以设置 Kmin = Kmax = K，并且 Pmax = 1。稍后我们会看到这不是最佳设置。
- NP**（接收方）** 算法：到达 NP**（接收方）** 的带有 ECN 标记的数据包表示网络拥塞。NP 将此信息传送回发送方。RoCEv2 标准为此定义了显式拥塞通知包 (CNP) 。NP 算法指定了 CNP 应该如何以及何时生对于每个流，该算法遵循图 6 中的状态机。如果一个流的标记数据包到达，并且在最后 N 微秒内没有为该流发送 CNP，则立即发送 CNP。然后，如果在该时间窗口内到达的任何数据包被标记，则 NIC 最多每 N 微秒为流生成一个 CNP 数据包。我们在部署中使用 N = 50µs。处理标记数据包和生成 CNP 是昂贵的操作，所以我们最小化每个标记数据包的活动。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWWj0CtGhPsnQzMZzCLa5ljIibhN40wjjC4JrsYibNh5JkWWLf6nZCMBI5dwKXLcql7gRAJ0OP7mwicQ/640?wx_fmt=png)

- RP 算法**（发送者）**：当一个 RP（即流发送者）得到一个 CNP**（显式拥塞通知包）**时，它降低它的当前速率（RC）并更新速率降低因子的值，α，像 DCTCP，并记住当前速率作为目标速率（RT）后来恢复。值更新如下：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWWj0CtGhPsnQzMZzCLa5ljlhz2b86Qia0PTRpM8pQebgU2BwPWqxfHib7Tqn4md7CFrEINXEbFGCTw/640?wx_fmt=png)

如果 NP **（接收方）**没有得到任何标记的数据包，则它不会产生任何反馈。因此，如果 RP**（发送者）** 在 K 个时间单位内没有得到反馈，它会更新 α，如等式 (2) 所示。请注意，K 必须大于 CNP **（显式拥塞通知包）**生成计时器。我们的实现使用 K = 55µs。

α = (1 − g)α,



此外，RP**（发送者）** 使用定时器和字节计数器以与 QCN相同的方式提高其发送速率。字节计数器每 B 字节增加一次速率，而定时器每 T 个时间单位增加一次速率。计时器确保流量即使在其速率下降到低值时也能快速恢复。可以调整这两个参数以实现所需的侵略性。速率增加有两个主要阶段：快速恢复，在 F = 5 次连续迭代中，速率快速增加到病房固定目标速率：

RC = (RT + RC )/2,



快速恢复之后是附加增加，其中当前速率缓慢接近目标速率，并且目标速率以固定步长 RAI 增加：

RT = RT + RAI , 

RC = (RT + RC )/2,



还有一个快速上升的超级增加阶段。请注意，没有慢启动阶段。当一个流开始时，如果没有来自主机的其他活动流，它会以全线速发送。此设计决策优化了流传输相对少量数据且网络不拥塞的常见情况 。



通过提供每流拥塞控制，DCQCN 克服了 PFC 的局限性。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWWj0CtGhPsnQzMZzCLa5lj4GicchiaRfwp012IvqfkXRX2Cn5hF0W8VgKic03Z0woeaFlmy0D4kSchA/640?wx_fmt=png)



图 8 显示 DCQCN 解决了图 3 中描述的不公平问题。所有四个流都获得相等的瓶颈带宽份额，并且差异很小。图 9 显示 DCQCN 解决了图 4 中描述的受害者流问题。



CNP 生成：DCQCN 对反向路径上的拥塞不是特别敏感，因为发送速率不依赖于准确的 RTT 估计。尽管如此，我们仍以高优先级发送 CNP（我们通常在Prio 发送CNP），以避免错过 CNP 截止日期，并实现更快的收敛。请注意，在没有拥塞的常见情况下不会生成 CNP。



**基于速率的拥塞控制：**DCQCN 是一种基于速率的拥塞控制方案。我们采用基于速率的方法，因为它比基于窗口的方法更容易实现，并且允许更细粒度的控制。



**参数：**DCQCN基于DCTCP和QCN，但在关键方面有所不同。因此，DCTCP 和QCN 推荐的参数设置不能盲目用于DCQCN。



**对 PFC 的需求：**DCQCN 并没有消除对 PFC 的需求。使用 DCQCN，流以线速开始。如果没有 PFC，这会导致数据包丢失和性能不佳。



**硬件实现：**NP 和 RP 状态机在 NIC 上实现。除了少量其他状态（例如 alpha 的当前值）之外，RP 状态机需要为每个速率受限的流保留一个计时器和一个计数器。这种状态在 NIC 芯片上保持。速率限制基于每个数据包的粒度。ConnectX-3 Pro 中 NP 状态机的实现可以以每 1-5 微秒一个的速率生成 CNP。在 40Gbps 的链路速率下，接收器可以每 50 微秒接收大约 166 个全尺寸（1500 字节 MTU）数据包。因此，NP 通常可以支持以所需速率生成 10-20 个拥塞流的 CNP。当前版本（ConnectX-4）可以为超过 200 个流以所需的速率生成 CNP。





**缓冲区设置**

DCQCN 的正确操作需要平衡两个相互冲突的要求：

(i) PFC 不会过早触发，即在给 ECN 发送拥塞反馈的机会之前。

(ii) PFC 不会太晚触发 - 从而导致由于缓冲区而导致数据包丢失溢出。



我们现在计算三个关键开关参数的值：tflight、tPFC 和 tECN ，以确保即使在最坏的情况下也能满足这两个要求。请注意，不同的交换机供应商对这些设置使用不同的术语；我们使用通用名称。讨论与任何共享缓冲区交换机相关，但计算特定于使用 Broadcom Trident II 芯片组的 Arista 7050QX32 等交换机。这些交换机具有 32 个全双工 40Gbps 端口、12MB 共享缓冲区并支持 8 个 PFC 优先级。



- Headroom buffer tflight：发送到上游设备的 PAUSE 消息需要一些时间才能到达并生效。为避免丢包，PAUSE 发送方必须保留足够的缓冲区来处理在此期间可能收到的任何数据包。这包括发送 PAUSE 时正在传输的数据包，以及上游设备在处理 PAUSE 消息时发送的数据包。最坏情况的计算必须考虑几个额外的因素（例如，交换机不能放弃它已经开始的数据包传输）[8]。遵循 [8] 中的指南，并假设 MTU 为 1500 字节，我们得到每个端口、每个优先级的 tf light = 22.4KB。
- PFC 阈值 tP F C ：这是在 PAUSE 消息发送到上游设备之前入口队列可以增长到的最大大小。每个 PFC 优先级在每个入口端口都有自己的队列。因此，如果总交换缓冲区为 B，并且有 n 个端口，则 tP F C ≤ (B-8ntf light)/(8n)。对于我们的开关，我们得到 tP F C ≤ 24.47KB。当队列低于 tP F C 两个 MTU 时，交换机发送 RESUME 消息。



- ECN 阈值 tECN ：一旦出口队列超过此阈值，交换机就会开始标记该队列上的数据包（图 5 中的 Kmin）。要使 DCQCN 有效，此阈值必须使得在交换机有机会使用 ECN 标记数据包之前未达到 PFC 阈值。



但是请注意，ECN 标记是在出口队列上完成的，而 PAUSE 消息是基于入口队列发送的。

因此，tECN 是出口队列阈值，而 tP F C 是入口队列阈值。



最坏的情况是所有出口队列上未决的数据包来自单个入口队列。为了保证在任何出口队列上触发 ECN 之前 PFC 不会在这个入口队列上触发，我们需要：tP FC > n ∗ tECN 使用 tP FC 值的上限，我们得到 tECN < 0.85KB。这小于一个 MTU，因此不可行。



然而，我们不仅不必使用 tP F C 的上限，我们甚至不必使用 tP F C 的固定值。由于交换机缓冲区在所有端口之间共享，tP F C 应该取决于有多少共享缓冲区是空闲的。直观地说，如果缓冲区大部分是空的，我们可以等待更长时间来触发 PAUSE。我们交换机中的 Trident II 芯片组允许我们配置参数 β，使得：tP F C = β(B − 8ntf light − s)/8，其中 s 是当前占用的缓冲区量。较高的 β 较少触发 PFC，而较低的值会更积极地触发 PFC。



请注意，s 等于所有出口队列中未决数据包的总和。因此，就在任何出口端口上触发 ECN 之前，我们有：s ≤ n ∗ tECN 。因此，为了确保 ECN 总是在 PFC 之前触发，我们设置：tECN < β(B − 8ntf light)/(8n(β + 1))。显然，较大的 β 为 tECN 留下了更多空间。在我们的测试平台中，我们使用 β = 8，这导致 tECN < 21.75KB。



讨论：以上分析是保守的，即使在最坏的情况下并且使用所有 8 个 PFC 优先级时，也可以确保 PFC 在 ECN 之前不会在我们的交换机上触发。优先级较少或交换机缓冲区较大时，阈值将不同。



该分析并不意味着永远不会触发 PFC。我们所确保的是，在任何交换机上，PFC 都不会在 ECN 之前触发。它发送方有一段时间接收 ECN 反馈并降低发送速率。在此期间，可能会触发 PFC。如前所述，我们依靠 PFC 来允许发送方以线速启动。**PFC是最后的杀手锏，简单粗暴。**

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWWj0CtGhPsnQzMZzCLa5ljkfzoCpxNfWkb1q0sX4TL2vH5CSwSZTHcrTRWhHsSJz4YaJpxvSu4qg/640?wx_fmt=png)





**三、DCQCN的不足**

然而，DCQCN在发生大规模的incast发生时，DCQCN会出现性能问题。当许多服务器同步发送数据给同一个接收者时，就会发生不同步。这种多对一的通信模式在很多数据中心都有应用，如MapReduce和 分布式存储（例如，Ceph）。DCQCN不能抑制当流量的数量超过数百个时，DCQCN无法抑制incast拥堵。此外，它还会通过持久的 PFC风暴，这反过来又会引起一些问题，如受害流和流量崩溃等问题。**Incast流量俗称“多打一”。DCQCN针对单个流拥塞控制没问题，但当多打一的情况比较多的时候，就会出现性能问题。**



固定的速率恢复期和固定的增加步长（即DCQCN中默认的55μs和40Mbps）对小规模的传输拥塞表现良好。随着传输流数量的增加，单个传输流的速率变得太小，甚至无法在单个速率恢复期发送一个数据包**（总带宽有限，传输流多了，单个传输流的速度上不去，在一个速率的恢复期一个包都没发完，速率又要调整了）**。**如果DCQCN使用固定的周期和步长来增加速率，针对小规模Incast可以，但当传输流数量增加后不合适。**





在DCQCN+中，我们可以使用CNP数据包的一个保留字段。发送端可以用这些信息估计规模，然后适当地更新他们的拥塞控制参数。首先，对拥堵规模的估计并不那么简单。一般来说，穿越同一个拥堵的交换机端口的流量可以有不同的发送方和接收方。对于在数据中心的部署，我们应该只使用功能有限的商品交换机。这意味着我们必须推断端点的拥堵规模。同时，对于原始协议的最小修改，拥塞规模的测量应该是简单的。其次，应该对协议进行额外的修改，使其在参数自适应变化时能够保持良好的工作。由于规模大，拥堵就很难排解掉。另一方面，对流量过度抑制的设计很容易造成吞吐量的损失。如果不对设计进行适当的补偿，自适应参数可能无法很好地工作。**针对于传统的DCQCN，好的优化方法是使用CNP数据包的一个保留字段，通过这个字段发件人判断拥塞参数的设置。**





DCQCN+可以提高RDMA网络中大规模传输拥堵的性能。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWvfsVEFiasEhjfMcibzIzoiceLcaBJXL65oRa4iaibicD6f28wntr748UY5Vw/640?wx_fmt=png)

DCQCN+使速率控制机制适应不同的情况。例如，它在网卡硬件能力的约束下自适应地分配CNP资源。我们在NS-3上为DCQCN+建立了一个仿真器，用于性能评估。此外，我们通过调整Mellanox ConnectX-4网卡的参数进行近似实验，以验证我们的设计要点。DCQCN+在仿真和测试平台上都能处理至少2000个流量的瞬时拥堵。在仿真中，其规模是DCQCN的10倍，在测试平台上是4倍。此外，DCQCN+的延迟也小10倍。



DCQCN需要端点上的网卡和交换机共同参与。



1) ECN配置。在交换机的出口队列中。数据包根据队列长度在ECN位上随机标记。如图1所示。RED被用于随机标记。当入口速率大于出口速率时，缓冲区会累积。当队列长度超过最小阈值时。数据包被标记在ECN位上，以表示拥堵。**现在网卡都是默认开启ECN。**

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVGicCdG2yloB8qwdPMuhWia0qgibheibYzeiaRox8Gc5PqE6RYYeiaWFnQjSXL4wQpgeVCnt9ia2CL06bnQ/640?wx_fmt=png)

为了获得低的排队延迟，DCQCN在交换机上保持低的缓冲区占用率。在10Gbps链路上，缓冲区内每个1KB大小的数据包会增加0.8us的排队时间。最大的ECN阈值（200KB）意味着10Gbps（40Gbps）链路的160μs（40μs）延迟，这是可以接受的最大值。平均队列长度较小.

2) 流速降低。只有在收到的数据包被标记在ECN位上,以及流量在一个固定的时期内没有被通知的情况下，接收方才会产生并向发送方发送一个CNP。考虑到网卡的CNP生成能力和在这段时间内可以收到的普通MTU（1,000B）的数据包数量，选择了50μs的值。实际上，这种设计的另一个考虑是等待和观察。尽管流量的速率已经被削减，但队列长度需要时间来减少。此外，该间隔还包括CNP传输的时间。发送者削减当前速率RC和目标速率RT如下。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWbcMiaT8Hw1pj6bicpdibia6smP70qrQex8eyewyCXCW2ibPhKF4ybicLpDSw/640?wx_fmt=png)

这里的α表示减少系数，g是预先配置的常数，Rmin表示流量的最小速率。Ratecut是微不足道的。如果在2个或更多的时期内收到CNP，α会增加，在下一次的时候，速率削减率会更大。接收器为每个流量维护一个时间计数器和一个字节计数器以及相应的状态位。还有一个状态计数器用来标志增加的状态。速率削减后，时间状态和字节状态被设置为0。



当一个流在K=55us的时间内没有收到CNP，它的时间状态会增加。当一个流已经发送了B字节而没有收到CNP时，其字节状态增加。当两个状态中的一个不是0时，该流开始以一分为二的方式恢复，时间为F=5轮，称为快速恢复（FR）。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWTyEFGsdrZiaFRURjj360mZmqKu4BTiceHqYGgNEkia1juz3k43LnzqyyA/640?wx_fmt=png)



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfW8skiayibmFQ7jicp39yRw6vh7cPAiapfxowmH6M8mDRRQIgQibAXzfdJWvQ/640?wx_fmt=png)

新一轮的开始是状态的增加。此后，可以触发加法增加（AI）和超法增加（HI）。在加法增加中，速率以固定的步骤RAI增加。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWwPWkiclsV4DLosIib7DSianA8QA0w0weria7yWj57W6pPAP7NcQianZK87g/640?wx_fmt=png)

当两种状态都超过F时，就会触发超速增长。在超速增长中，速率呈现指数式增长，参数RHAI：当两种状态都超过F时，就会触发超速增长。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWticca7DiaFxL65wRSLicmHibIq5uQI7HjcuIu1a2WvLnqXOcuLdUvBr3aA/640?wx_fmt=png)

其中

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVGicCdG2yloB8qwdPMuhWia0hjFicR9wp1A7uav9buWcUAXHOEPkbkX5y2AnWSfQR89kSUAG6rYK4gg/640?wx_fmt=png)



在每次恢复时，α也将减少。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWHfH50NSNIGUjVKJJibicTKQliau5UR19pWohUGbia069DLCL0IX5IIFia9A/640?wx_fmt=png)

4) 线速策略。在DCQCN中，流量以线率开始，以获得链路的充分利用。然而，线速是如此激进，以至于随着拥挤流量的增加，琐碎的速率削减需要更多的时间才能生效。在这段时间内，队列长度大到足以触发PFC。如果流速最终能被压低，那么缓冲区就会被耗尽。但如果流速没有得到适当的抑制，由PFC引起的暂停将持续到拥堵流量的结束，这对性能是一个很大的伤害。





DCQCN的设计者Yibo Zhu已经在NS-3上发布了DCQCN的仿真。我们在测试平台上使用了9台带有Mellanox ConnectX-4NICs（简称CX4）的主机和1台Mellanox SN-2700交换机。如图2所示，使用了8:1的Incast拓扑结构。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVGicCdG2yloB8qwdPMuhWia004EiafrVr5PUPWN9Hv67kiaC4I2oBc7GkRnLR8sA6cz0F1OImsic3icjyA/640?wx_fmt=png)







对于大规模的拥堵，每个发送方都有相同数量的流开始。在测试平台的实验中，我们使用libpcap来捕获数据包进行吞吐量统计。为了触发libpcap的traps，我们必须打开网卡上的sniffer。然而，这个功能对网卡来说是一个沉重的负担。打开sniffer后，我们只能捕获大约18Gbps的吞吐量。所以libpcapis只在图3的实验中使用，其中链接被限制在10Gbps。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39Lkrc5s8iaIcVlKo6teE0RPJGPEKHYHXpicEVxrPXUzx5lInPUfHiansjjibJWg/640?wx_fmt=png)



这是必要的，因为我们必须清楚地观察DCQCN和CX4是如何工作的，以了解它们的区别。在其他测试平台实验中，我们关闭sniffer以防止性能损失。我们使用Perftestpackage中的工具ib send lat来测试流量的延时。最大的缓冲区使用量可以从交换机上的计数器得知。





B. DCQCN和CX4实现之间的差异我们已经观察到，的DCQCN和Mellanox CX4实现之间有一些差异。然而，CX4的固件中的专有算法一直在更新。此外，推荐的参数是根据其实际部署环境调整的。因此，只有通过对参数和实验结果的比较，我们才能了解到这些差异。表一显示了一些参数的对比。请注意，在CX4的实现中，cnps之间的最小时间（DCQCN中的CNP间隔）默认设置为0，这似乎太小了。然而，通过测量CNP之间的间隔，我们已经验证了每个流量的CNP间隔是完全由参数确定的cnps之间的时间控制的。这意味着，NIC将为其收到的每个ECN标记的数据包发送CNP。使用如此低的CNP间隔，当拥堵发生时，连续的数据包被标记，这将导致过度的速率削减。为了防止这种情况，**CX4使用了一个新的参数rate reduce monitor period（默认为4μs），它代表了两个rate reduction之间的最小时间间隔。**我们注意到，在这样的参数下，速率的增加应该更少更慢，这意味着速率削减后的收敛时间更长。然而，这个结果并不明显，因为模拟和测试平台的结果之间的差异并不明显。我们怀疑它们之间还存在着其他的调整。为了说明这一点，我们用CX4参数配置了我们的模拟，并进行了一个简单的实验。4个主机用10Gbps的链路连接到一个交换机上，3个发送者分别向唯一的接收者发起一个流。图3显示了在CX4和仿真中流速随时间变化的情况。在CX4实现中，流速收敛的速度比相同参数下的仿真快得多。虽然有不同的速度，但拥塞的故障在CX4的模拟和测试平台中都有发生。此外，我们在仿真和CX4实现中都验证了我们的解释和设计。因此，我们的结果既适用于最初的DCQCN，也适用于CX4的实现。



C. DCQCN在大规模incast时的失败我们观察到，在仿真和测试平台实验中，当大规模incast发生时，拥塞点的开关缓冲队列长度保持一个非常大的值。这表明DCQCN的收敛失败。在实验中，我们使用了一个由9台主机和1台交换机组成的嵌套拓扑结构，如图2所示，在仿真和测试平台中都是如此。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcOdYLdTsJdPDl1Y0cqB1aIlV9jJyiaJw9IkrHOht1z5sJYQ7u12XiaIhg/640?wx_fmt=png)







8个发送者开始发送相同数量的流量，并持续发送，直到实验结束。图4显示了NS-3[8]仿真中缓冲区队列长度和流量数量之间的关系。在仿真中，采用了DCQCN的默认参数。对于10Gbps链路，我们用40Gbps链路的1/4的速率增加（如RAI）的参数进行了另一个实验。如图所示，

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcXWNzlANEcEvRlghg8b2Q1OqrhFtatwbMIicurfsAVy798DuttoETCicw/640?wx_fmt=png)



在10Gbps(40Gbps)链路的约80(160)个flows下，DCQCN工作得很差，拥塞无法得到缓解。图4(c)显示了CX4实现中平均延迟、最大缓冲区大小和流量数量的关系。5秒对于流量来说是足够长的时间来降低速率和消除拥堵，因为它是成千上万的一个周期。我们可以看到，在大约480-560个流量的情况下，CX4已经无法处理拥堵问题。最大的缓冲区使用量超过4MB，大的缓冲区队列导致极长的平均延迟。平均延迟约2000μs意味着平均2.5MB的缓冲区。PFC必须一直工作以防止数据包丢失。由于我们所讨论的DCQCN和CX4实现中的参数差异，规模比模拟结果要大。我们已经验证了当使用CX4模拟的参数时，最大的规模也是480-560流量。然而，在下面的讨论中，我们将看到，简单地使用不同的参数并不是一个适合大规模传输的解决方案。



在我们的设计中，同一接收方的所有拥堵流通过时间复用平等地分享CNP。因此，CNP周期可以反映出接收器上拥挤流量的数量。我们利用CNPs中的一个可用字段来承载CNP周期，而不使用额外的信号包。关于拥堵的第二件事是流速本身。一般来说，速率较大的流量在拥塞队列中有更多的数据包，因此有更大的可能性数据包，它将收到一个CNP并降低速率。因此，当收敛时，所有拥挤的流量都有几乎相同的速率，这与流量数量有关。



如何根据CNP周期和流量速率选择参数是另一个问题。有两个设计点。（1）恢复定时器应该总是大于CNP周期，以接收CNP。此外，它应该足够大，以满足至少发送一个数据包的速率。基本上，我们可以将它们的最大值设置为恢复定时器。此外，我们使用一个松弛比率λ（λ>1）。(2) 总吞吐量的增加不应该随着拥堵流量数量的增加而增加。因此，增加步骤RAI应该与流量成正比。所以我们使用一个额外的指数增长阶段HI。虽然与DCQCN中的增量阶段名称相同，但这与DCQCN的设计有些不同，因为这个指数增长与流速有关，而不是与一个常数有关。此外，在DCQCN+中，小流量比DCQCN中更容易触发HI。在HI中，小流量可以在10次迭代中增加1000倍。一般来说，DCQCN+对其基于这种设计的参数不是很敏感。动态参数方案使DCQCN+与静态DCQCN相比不太敏感。就像DCQCN一样，DCQCN+可以被分为3个逻辑部分。就像DCQCN一样，DCQCN+可以分为3个逻辑部分：拥堵点（CP）、通知点（NP）和反应点（RP）。我们分别讨论每个部分。



B. 设计细节1) CP算法。DCQCN+使用与DCQCN相同的CP算法，因为一个友好部署的解决方案对交换机的要求总是很低。交换机为ECN标记配置了RED，如图1，但最小和最大标记阈值为20KB和200KB。在这里，我们使用一个大的最小标记阈值来保证更高的带宽。5KB，即5个数据包，对于实际环境和大规模场景来说是有点浅的。我们的PFC配置与[5]中的DCQCN相同。这个配置在设计DCQCN的时候已经被计算和验证过了。正如我们提到的，CNP在拥塞控制中起着重要作用。在CNP供应不足的情况下，流速有可能永远不会收敛。DCQCN认为NIC可以按照自己的意愿生成CNP。不同的是，在我们的设计中，NIC的CNP生成能力在NP中得到了考虑。每个流量的CNP间隔被要求是相当固定的，以便设置恢复计时器。为了实现这一点，NP维护一个所有拥堵流量的列表，并遍历该列表，为已经收到ECN标记数据包的流量发送CNP。列表中的一条记录包含流量标识、ECN位和时间字段。如果收到一个ECN标记的数据包，NP将把记录的ECN位设置为1。NP每次检查一条记录，以决定是否为该流量发送CNP。如果ECN位被设置为1，并且该流有一段时间没有发送CNP（最小CNP间隔，默认为45μs），则将发送CNP。写入CNP通知RP的CNP周期τ表示检查同一流量记录的时间跨度，可以通过CNP生成间隔δ和列表长度l计算如下。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWGIbCog7gsd1jw6NdchQcyI6CPicpicKEow3m80fmibgCePLic8iaRSYpnfQ/640?wx_fmt=png)

一旦NP发送了一个CNP，它就会重置ECN位和它在列表中发送这个CNP的时间。我们使用CNP数据包的储备字段[2]来向发送方明确传递CNP周期，因此，发送方可以根据这个值来设置定时器。这个字段是16字节，现在还没有使用。



3）RP算法：当RP收到一个CNP时，它像DCQCN一样降低流量的目标速率和当前速率RT、RC。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWhicAKKibCFe3CjK2bt9frb1bqVfzf5T5F58MHOFBO5JoOTDPYQjyNCTQ/640?wx_fmt=png)

此外，还有一个最小速率保护Rmin。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWQdyI7V36wLeNP7tefNr07icagDibBzibrftMk6lCnZ5VjuCSQALYUwic8A/640?wx_fmt=png)

需要注意的是，最小的速率给出了流量的上限，我们在10,000个流量的边界上使用了一个小值Rmin=RC/10000.每个流量都有用于速率恢复和更新α的计时器。当一个定时器过期时，相应的更新被处理。RP从CNP的PSN字段中获得CNP间隔，并根据它重置定时器。计时器必须足够长，以便流量能够发送多个数据包，并且不能短于CNP周期。因此，如果CNP间隔τ大于50us，α的定时器更新Kα和速率增加的定时器K将更新如下。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWempzia6CsHByO4FiaWft6lPkE8Wwe73jw3iauUpmyaMCckFBzcAJI6I6A/640?wx_fmt=png)

其中，M表示数据包的最大MTU，λ，λα是扩大的比率。在我们的实验中，M被设置为1000KB，λα被设置为1，λ被设置为2。一个状态计数器S被用来表示速率恢复的不同阶段。当速率恢复计时器过期时，状态会增加1。如果状态小于阈值F=5，流速会像DCQCN中的FR一样增加。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWcA4DUUPBVYficdJGmBmLTgkf1AKP0Jyic6JICPrP7sOJeibHQ6QPW0uxQ/640?wx_fmt=png)

如果状态大于F但小于4F，则采用不同的AI 的增加被使用。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfW7XzTPwlLAzpyPBBv9eYLD6LbQicaCPclewLbCpT0bdRfibvKGy1xnTicQ/640?wx_fmt=png)

否则和目前的加价方式一样。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWMicFLCH0gibjdRqEaIy7DiczUPiaThO8CVAfCx9XpK9WJeoDBFfU0WPnKg/640?wx_fmt=png)

这里Rl表示链路容量。请注意，当α不同时，我们使用不同的增加步骤。当α大时，使用较大的步长以实现快速恢复。小的α意味着流速接近收敛，所以应该设置较小的步长。增加的步长RAI是以当前速率的比率形式计算的，因此拥塞点的总吞吐量增加只与现在的总吞吐量有关，不会随着流量数量的增加而增加。此外，我们使用一个Rl的比率来约束小流量情况下的增加步骤，根据我们的实验，这是有必要的，如果状态超过4F，则使用HI增加。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWO2xKelGmPazYibdLLficbjVYIgaUpuFLhz3WUZzs6T2cqUqWnB0JgFAg/640?wx_fmt=png)

在HI阶段，小流量只需要10个周期就能增长1000倍，以保证高带宽。在HI阶段，小流量只需要10个周期就能增长1000倍，这个增长也是由另一个不考虑流量的指数增长步骤来限制的，以保护大流量的情况。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfW7BryNuHYT8eebUpJGjibql04SZVPyMhnSKCsvg3LW9nIIXhtQD9LibsA/640?wx_fmt=png)

在我们的设计中，我们没有使用字节计数器，因为在不同的定时器下，速率的增加将是不明确的。实际上，在DCQCN中，即使在40Gbps的速率下，发送10MB的数据来增加状态也需要2ms。这是恢复时间的40倍，在使用10Gbps链路时甚至更大。这种配置的设计对恢复的影响很小。  

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWRYL55sbqcbucDzddSicPjORGQs2gwxn2FbVXyZLBta6ugib9kibprlQIQ/640?wx_fmt=png)

V. 评估.

A. 大规模Incast

大规模传输 DCQCN+的最初设计目标是处理大规模传输问题。为了验证我们的设计，我们在模拟中测试了DCQCN+在大规模传送下的性能。如图2所示，我们使用8个发送方和1个接收方的传送拓扑结构。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVGicCdG2yloB8qwdPMuhWia004EiafrVr5PUPWN9Hv67kiaC4I2oBc7GkRnLR8sA6cz0F1OImsic3icjyA/640?wx_fmt=png)



每个发件人开始相同数量的流。为了保证传输，所有流量都是在0.1秒内的统一随机时间开始的。图6(a)(b)显示了拥塞点的队列长度随着流量数量的增加而变化。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVGicCdG2yloB8qwdPMuhWia0ddzpKIm0s62o4d66hlOVnL8NexwoP8ic152nSSAyX1S4A1Z2zOWNa4g/640?wx_fmt=png)





我们可以看到，DCQCN+在10Gbps和40Gbps链路上都能处理至少2000个流量的拥堵。当流量收敛时，拥塞点的队列长度被限定在200KB左右。在最坏的情况下，在所有流量开始后，交换机的缓冲区可以在大约0.1秒内被压制。记得在图4中，DCQCN在同一场景下不能排掉多达160个流量的拥堵。当使用DCQCN时，队列长度是PFC所能阻止的最大值，即4.9MB。DCQCN+有20倍的队列长度，这意味着20倍的排队延时。此外，它不会受到PFC风暴造成的副作用的影响，而DCQCN会。然而，我们认为在更大规模的传输中进行模拟是不现实的，因为其他部分（例如，NIC的队列对）可能是系统的瓶颈。这个约束并不严格，因为流速必须低于某个时间段的收敛率，才能排解拥堵。如果我们想处理更大的规模，我们可以使用更小的Rmin。TIMELY是RoCEv2的另一个基于RTT的拥堵控制方案。对DCQCN和TIMELY在不同方面的性能进行了比较，并声称与延迟相比，ECN是一个更好的拥塞信号。我们使用NS3上的TIMELY仿真来了解TIMELY是如何处理大规模拥塞的，进行比较。



图7显示了TIMELY在大规模拥塞下的表现。TIMELY比DCQCN好得多，在1200个流量的规模下，TIMELY仍然可以限制拥塞点的队列长度，但是，由于缺乏专门的设计，TIMELY在更大的规模下仍然失败。此外，流量的吞吐量是非常不稳定的，当流量数量大的时候，吞吐量有点低。吞吐量的损失主要发生在拥堵结束后的短暂恢复时间内。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVGicCdG2yloB8qwdPMuhWia0kVwwMCXibzH6hNAq4F8I0Uric27wkTsyrQdWAePRXNGxficjrfU8LVxzg/640?wx_fmt=png)



图6(c)(d)显示了随着流量数量的增加，总吞吐量和时间之间的关系。请注意，当我们谈论吞吐量时，我们指的是通过计算所有发送者在固定时间跨度内发送的数据包大小来计算的总发送率。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVGicCdG2yloB8qwdPMuhWia0ddzpKIm0s62o4d66hlOVnL8NexwoP8ic152nSSAyX1S4A1Z2zOWNa4g/640?wx_fmt=png)







这个值更有意思，因为我们可以看到当DCQCN+工作时，总速率是如何变化的。在PFC的保护下没有数据包丢失，所以发送方的所有吞吐量都是有效的。我们可以看到，吞吐量损失总是小于0.1秒，这是一个可以接受的代价。



B. 小规模传输关注DCQCN+在小规模传输场景中的收敛和性能也很重要。我们使用相同的传输拓扑结构进行了3:1的传输模拟来验证这一点。图8(a)(b)(d)(e)显示了10Gbps和40Gbps链路上的流率变化。DCQCN和DCQCN+中的流量收敛情况类似。流量的速率在很短的时间内被削减，并以很小的变化收敛。图8(c)(f)显示了总吞吐量，DCQCN+在10Gbps链路上的变化比DCQCN小。在40Gbps链路上，DCQCN+的吞吐量和流量完成时间与DCQCN相似，但在10Gbps链路上的吞吐量较低（约4%）。这一损失可以通过更细致的设计或参数调整来弥补，特别是在RAI上。然而，这是一个可以接受的损失。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWlMo3QWy2zh5STY7hnjMH2FZcUOiaQWZOanYF7bWByQRyn4pO919dH3w/640?wx_fmt=png)

C. 大型拓扑结构在大规模传输测试中，我们在8台主机上使用不同数量的流量来获得大型传输。然而，今天的数据中心网络有数百或数千台主机，使用CLOS拓扑结构。为了实用，我们应该在这样的环境中进行模拟。我们建立了一个类似于2410个节点的CLOS拓扑结构，并在这样的拓扑结构中测试DCQCN+的incast场景。所有流量都是在0.1秒内随机开始的。图9显示了总吞吐量和交换机的缓冲区变化的一个例子。缓冲区可以像我们预期的那样被削减到200KB以下。总吞吐量收敛到400Gbps，这相当于10个接收器的总吞吐量。请注意，我们的吞吐量是指所有发送者的总吞吐量，因此吞吐量在开始时大于400Gbps，并且在短时间内较低，以耗尽缓冲队列。融合时的平均吞吐量约为95%。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39Lkrcdy2jJgRGZHeGI1wYvPIkh9fashYVBBWoYwwBb1MaLJKPrNykm1ZZiag/640?wx_fmt=png)







D. 测试平台近似为了验证我们的设计，我们想出了一种方法，在我们的测试平台上使用CX4网卡来模拟DCQCN+。DCQCN+设计的关键点是为不同的场景使用不同的参数。在参数相似的情况下，DCQCN+和DCQCN的工作原理相似。因此，我们可以使用DCQCN+在收敛点的静态参数来模仿DCQCN+。例如，对于540个流的转换，我们将CX4配置为

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXgCLg9K1mHnk2iabYY1aHfWf16siaSf8OP1sUu5EGiciaZtOqicFN726NibqjrgRlAqN3spiaInmDRAvm5w/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVGicCdG2yloB8qwdPMuhWia0Jt9TWnnILSeC5MNbXTXCfQ58BziaHrcyTkeiaLRMfTVnjeV8Hicm6bO2g/640?wx_fmt=png)

由于DCQCN+根据流速和流量数量调整其参数，在流量的开始和结束时，DCQCN+的CNP周期较小，RAI较大。但这些参数与DCQCN+在相同场景下收敛时的参数接近。在这种情况下，DCQCN达到收敛的时间要慢得多，但它们的收敛状态相似。图10显示了在我们的试验平台上进行的此类实验的结果。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcRdpuiaSPCGSEZmKeFSeyzwW59IgKlIYvxBjPTUkrbq2qmiayejYl0nYA/640?wx_fmt=png)





我们在10Gbps链路上使用了图2的incast拓扑结构。在这里，我们选择了一些接近CX4失败的阈值的流数和一个更大的流数来显示可扩展性。我们可以看到，近似值，即具有静态DCQCN+参数的CX4，在实际环境中对大的incast是有效的，拥堵耗尽，队列长度很短。在这种情况下，使用这些参数可以获得10倍的缓冲区队列长度和延迟。





E. 现实的工作负载为了测试DCQCN+在现实工作负载下的性能，我们在NS3中进行了实验。仍然使用传送拓扑结构，但这次所有主机都可以是发送方和接收方。我们根据负载和工作负载中的流量大小分布，生成受泊松过程影响的流量。图11显示了不同流量完成时间（FCT）下的流量数量。FCT是用1μs到106μs的对数尺度测量的。与DCQCN相比，DCQCN+的流量完成时间略小，分布也相似。这并不出乎意料，因为在这种现实的工作负载模型中并不存在这种情况。一个发送方或接收方的最大流量数量约为200，而且这些流量不会同时运行。因此，不对称程度甚至要小得多。在这种情况下，DCQCN+的性能与DCQCN的性能相似，并有有限的改进。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcxHE9a3f1CgiaPgRjCT6blALWftRBk7a4G8KF4oAZaFLCCcFULTfz09g/640?wx_fmt=png)

A. 收敛性和适应性

DCQCN+通过计算CNP携带的信息来调整定时器的值，所以它对大流量和小流量都有适应性。对于收敛性，我们可以确保在增加的时间间隔内至少有一个数据包被发送，如果RP收到一个ECN标记的数据包，在下一个时间段可以发送一个CNP。这种保证与流量、流数或CNP生成能力无关。因此，在大多数情况下，如果需要，速率削减总是发生在增加之前。此外，即使流量的数量很大，小概率丢失速率降低的影响也很小。因此，我们相信这种设计在大多数情况下是非常强大的。我们的模拟显示了它在2000个流量下的力量。例如，为了获得更高的吞吐量，我们考虑使用一个较低的速率切割比的方程式。这个值，也就是α的系数，默认为1/2。图12(c)(d)显示了使用不同最大速率切割比的缓冲队列长度和吞吐量。







我们使用720个流量，在10Gbps链路的8:1 inast拓扑结构下，所有流量在0.1秒内随机启动。在较高的最大削减率下，DCQCN+能更快地排掉拥塞，但同时也有较大的吞吐量损失。可以根据需求进行选择，但我们建议使用1/2，我们的其他仿真结果也是基于这个值的。实际上，DCQCN+对这种参数调整不是很敏感。图12(a)(b)显示了使用不同时间的HI参数时DCQCN+的性能。这里我们使用图2中的incast拓扑结构。嵌套比例为1200:1，链接速度为10Gbps。DCQCN+的工作性能很高，除非参数非常极端（5×HI）。5×意味着在HI增加时，流量增加1Gbps或速率增加一倍。我们认为重要的是动态的模式而不是参数。为了进一步讨论，我们计划在未来的工作中证明DCQCN+的稳定性时，研究基于数学分析的参数的影响。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcH02O2WkVmQF9iclfsnodEiarxtib0sYmvgMjckQN9foqGPNHVKKxS5k4A/640?wx_fmt=png)

C. 公平性公平性也是网络流量的一个重要指标。在DCQCN+中，在一个拥堵点，所有拥堵的流量都平等地分享链接容量。这是由线性ECN标记概率保证的，因为大流量有更大的可能性被标记，从而被切断。我们使用流量完成时间的CDF来衡量公平性。我们使用图2中40Gbps链路的拓扑结构，将我们的设计与DCQCN进行了小规模和大规模的比较。图13(a)显示了总共8个流量的CDF。每个流有10,000个1000KB的包，并在同一时间精确地开始。我们可以看到，在这种情况下，DCQCN+更加公平，平均完成时间比DCQCN小。图13(b)显示了总共800个流量的CDF，即每个主机100个流量。模仿真实环境，所有流量都是在统一的随机时间（0,1）微秒内开始。每个流有30,000个1,000B的数据包。在这种情况下，DCQCN不能缓解拥堵，PFC持续到最后。流量是定期暂停和恢复的，因此DCQCN的公平性很好。不足为奇的是，DCQCN+在大流量情况下并不那么公平，因为恢复速度非常快，因此抖动可能会造成目标吞吐量的差异。无论如何，在这种情况下，DCQCN+的最大流量完成时间只比DCQCN长4%，而且平均流量完成时间仍然更好。







D. 实施成本讨论实施DCQCN+和在数据中心部署它的成本是有价值的。DCQCN+在端点上完成大部分工作，因此它对交换机没有特殊要求。基本上，应该配备PFC和基于RED的ECN。应支持优先传输控制信号，如CNP。NP算法在智能网卡中实现。NIC必须查询、插入、更新和删除流量列表。与DCQCN相比，这是一个额外的计算成本。列表中的一条记录最多需要3个字节用于流量识别，1个字节用于ECN位，4个字节用于记录最后的CNP时间，因此我们每条记录需要8个字节。总而言之，列表的大小每125个流量增加1KB。这是一个可以承受的空间成本。幸运的是，我们在更新时不需要锁定列表，因为最坏的结果是增加或丢失一个CNP。这些要求与DCQCN的要求相同，因此可以实现。


E. PFC对速率恢复的影响人们可能会考虑到由PFCh引起的流量暂停对速率恢复的影响，并认为这是DCQCN失败的一个可能的原因。一个合理的选择是在优先级队列暂停时暂停相应的定时器。但是要暂停一个定时器对于网卡的硬件实现来说可能不是那么容易。此外，我们发现这在我们的实验中实际上并不重要。DCQCN在没有它的情况下会打破收敛，而我们的设计仍然可以工作。但为了稳健起见，我们在DCQCN+中使用了一个简化的解决方案。当一个定时器失效时，我们首先检查该流的优先级队列的暂停状态，只有当这个队列没有暂停时才进行速率恢复和状态增加。这就更容易实现了，而且可以限制暂停流量的恢复。



**22.RDMA流量抓包分析**

在此前文章中，笔者分享过IBA的四种Operations，本文对前三种进行抓包分析，即IB Send/Rec、RDMA Read、RDMA Write。

[Infiniband协议代码分析](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663510071&idx=1&sn=6a81ebc786b356c289a93c75e4328027&chksm=81d6b74fb6a13e59833401c798bd4f4d2c74ac8d6a0a9ca47b78948044928d50efd6a0d5853e&scene=21#wechat_redirect)



**获取RDMA流量**

新版本的OFED驱动，已经支持tcpdump抓取RDMA流量。但需要libpcap1.9及以上的支持。 如果低于1.9，需要手工编译升级一下。

1. git clone https://github.com/the-tcpdump-group/libpcap.git
2. cd libpcap/
3. yum install libnl3*
4. ./configure --enable-rdma --prefix=/usr --sysconfdir=/etc --libdir=/usr/lib64
5. make -j 8
6. Only in case you can install on a system, run:
7. make install



确认网卡的sniffer已经开启：

\#tcpdump

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF14LBc28teMKWCfIUl7aazSPnFRMUZFTMzMKHZN1xqtCLOk1x4gfgfYw/640?wx_fmt=png)



**抓包分析**

OFED 5.1版本以上，通过tcpcdump对 mlx设备进行抓包（对网卡设备en是抓不到的）。

我们使用一台服务器，使用ib cli自己压自己。

```
# ofed_info -sMLNX_OFED_LINUX-5.5-1.0.3.2:# uname -aLinux l-csi-c6420d-03 4.18.0-348.2.1.el8_5.x86_64 #1 SMP Tue Nov 16 14:42:35 UTC 2021 x86_64 x86_64 x86_64 GNU/Linux# cat /etc/redhat-releaseCentOS Linux release 8.5.2111# rpm -qa |grep -i libpcaplibpcap-1.9.1-5.el8.x86_64
```



收集tcpdump的时候，注意不要时间太长，否则dump文件太大。
写

```
收集clitcpdump -i mlx5_0 -s 65535 -w rdma_write.pcapServerib_write_bw --tclass=106 -a -d mlx5_0Clientib_write_bw -a -F 10.7.159.71 --tclass=106 -d mlx5_0 --report_gbits
```





读

```
收集clitcpdump -i mlx5_0 -s 65535 -w rdma_read.pcapServerib_read_bw --tclass=106 -a -d mlx5_0Clientib_read_bw -a -F 10.7.159.71 --tclass=106 -d mlx5_0 --report_gbits
```



发

```
收集clitcpdump -i mlx5_0 -s 65535 -w rdma_send.pcapServerib_send_bw --tclass=106 -a -d mlx5_0Clientib_send_bw -a -F 10.7.159.71 --tclass=106 -d mlx5_0 --report_gbits
```





**RDMA Write文件**

通过WireShark打开下载的文件。先分析RDMA Read。

我们对报文进行分类，四类报文，两个QP：

QP 90：

- RC RDMA Write Only

- RC RDMA Write Middle

- RC RDMA Write Last

  

QP 91:

RC Acknowledge

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1ibwbY5MUQWnsHMokw6BfZxBHghmA96Cza13FWlJ0g3nV8tBvDYgL9pw/640?wx_fmt=png)



有RC Acknowledge:

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1FH6bqjHsliak3iaMsD2JlVSmhIT3qvVXiacW4vO9qAxlIxvnccUa81wvQ/640?wx_fmt=png)

有RC RDMA Write Middle：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1drueyjVBibpep0C8gNwRGPFRmJgAOWud2XVsANibp3mFebvicZt603TMg/640?wx_fmt=png)

RC RDMA Write Last

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF181PYUogAtiaiacw2gVibRnByEmKS8ybx2fWQfW9rTfiaSNgcDZqIHOrF7g/640?wx_fmt=png)



我们查看一条RDMA Write Only的报文，分为几部分。

帧的类型是UDP：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1ticvJK8k1ZjYRdDQ5ibsLP9XHjJKiaibt9vJpcNkWmdp7a74pvZZ1aNBqg/640?wx_fmt=png)

源和目标的网卡的PCI地址

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1XmsH7ibLspsPJDNYe2BLlAn0RkL7f6mwA4DXG8ibprMvqB3ESlzB9LuQ/640?wx_fmt=png)



Internet协议层。有源和目标IP、DSCP、ECN标志位。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1jaBcu273icF5sQWSlClq0n3aF31epgibzEh5sKq5cggbYczmIj5btN3g/640?wx_fmt=png)

查看UDP数据报协议层，可以看到源和目标的Port：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1KiaFwib5dVO2wpUsfbWthk1mWscqZr7Y7eV12scAQu2pN4rCUXExrxHQ/640?wx_fmt=png)



查看Infiniband层：RC模式、RDMA READ Request、目标QP、虚拟地址、Remote Key等信息。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1ibLOMWI6TlnMLQOESERBvakTibuibgkGKAr9H6iaVecVbicrjTLWbNGd4DQ/640?wx_fmt=png)



数据层：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1xZxMGmOzZjlPHTJlSVuayf8Fal0ibPAviauf3HsUpXYU5qArcRRX93Ww/640?wx_fmt=png)



我们查看一条RC Acknowledge的报文。这个报文使用的QP和RDMA Write Only的报文是不同的。我们看报文的几部分。从结构看，和RC Acknowledge的报文没区别。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF18kehYjaq5lNhx9QMaBKO0w6HCXdADtS0TAdahFTIrj4wrb6Y09WKAg/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1AZbL8rH7yo0KKhOWwxqIiaJ0tQKibdqhrLZo5WgkYVX3ibThBcLKDiaQUQ/640?wx_fmt=png)







**RDMA Send文件**

分析RDMA Send文件，有三种报文。分属两个QP。

QP 94:

- RC Send Only
- RC Send Middle



QP 95

- RC Acknowledge



我们查看RC Send Only：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1lWNXetGg8dEvfYkZVibQbJe22GCTicUicZQtRTfph6wBQLAzUJcDyWia0Q/640?wx_fmt=png)





![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF14hFdReQXkhqmgR2sqxMUjkhVkJEChF2B7icFnKoFvBM6cXzK8IBTLcg/640?wx_fmt=png)





![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF16frkVib1uxPSqic6N8JibceIhgA4BCYiaEeiciaHBJxor83oMKgbyXRohQQQ/640?wx_fmt=png)



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1VDxzFiaoibjNGeTcN6jorlGJaGppZ8jxwO9NSOic32EfvYhzLAQxI1DGQ/640?wx_fmt=png)





![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1SEJKtptHrYCI0PdDficwb291icxibzhV51GybV6ZicujoKY1eo2wricm0wg/640?wx_fmt=png)





**RDMA Read文件**

分析RDMA Read文件。我们看有几种报文：

QP 92:

- RC RDMA Read Request

QP 93:

- RC RDMA Read Response First
- RC RDMA Read Response Only
- RC RDMA Read Response Middle
- RC RDMA Read Response Last



由于报文架构相同，只是字段不同，我们不再赘述。



**总结**

上面三个测试，之所有每个文件包含的报文类型不同，和三种IBA Operation有直接关系。

如下图所示，Send/Rev和RDMA Write有ACK，而RDMA Read没有。这与上面的抓包分析结果完全一致。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVG5HOqMxsWvrQsFlYdBOF1gkBd6jS4OFtMkwfu56Hicsv2JzcZdRiazdfNHP63oLrO6vyibz5vwxtug/640?wx_fmt=png)



**23.PFC与ECN: RoCE的实战系列1**

**RoCEv2概览**

我们知道，RoCEv2保留了IB传输层，但用IP和UDP封装代替了IB网络层（L3），用以太网代替了IB L2（如下图所示）。IB协议对丢包很敏感。所以RoCE的网卡和交换机的很多技术，为围绕着怎么让网络不丢包、少丢包展开的。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVq2qGD6CQrJ9NGAJF0zn8ThvNClKicNZMC4QU1CwYQTIuTKNl8lLRLric1gNUB37KSP2yDhB2IhkkQ/640?wx_fmt=png)





围绕着如何防止丢包，RoCE相关技术分为两大块：

- 防拥塞技术：比较典型的是PFC、ECN、DCQCN
- QoS技术：PCP（+DEI）、DSCP





**我们先看看拥塞控制技术。**

首先讲，三个防拥塞PFC、ECN、DCQCN都是在交换机上实现的。当然，这些技术对网卡同样有要求。



PFC（Priority-based Flow Control）: 是在交换机入口（ingress port）基于优先级实现的流量控制。在无阻塞的情况下，交换机的入口buffer不需要存储数据。当交换机的出口的buffer到达一定阈值后，交换机的入口buffer开始积累，当入口buffer达到我们设定的阈值时，交换机入口开始主动迫使他的上级端口降速。



以下图交换机B为例，G0/2是入口；F0/1是出口。入口和出口都有buffer。阻塞的时候，入口Buffer用不上，因为网络包向交换机传递很顺畅，没堵。如果网络发生拥堵，那么交换机B的出口的buffer开始淤积，到达一定阈值后，交换机B的入口开始淤积，当buffer到达一定阈值后，交换机B要求交换机A的G0/1降速。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVq2qGD6CQrJ9NGAJF0zn8T8ve34DcQPuCOOSNfNXm41Bo0icREww3TUMZANAuktpZkU7zNnTs0uwg/640?wx_fmt=png)



PFC允许在一条以太网链路上创建8个虚拟通道，并未每条虚拟通道制定一定优先级，允许单独暂停和重启其中任意一条虚拟通道，同时允许其他通道的流量无中断通过。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVq2qGD6CQrJ9NGAJF0zn8TmDCuZ61QpXJGwrtmn5EMuFyf7mXmRJgM1dvFqWNKzoc8vBXUaNOJ0g/640?wx_fmt=png)接下来，我们看一下PFC的具体配置。

https://community.mellanox.com/s/article/howto-configure-pfc-on-connectx-4



在Linux中配置CX-4网卡的PFC优先级。

默认网卡7个PFC优先级都没开启：

```
# mlnx_qos -i eth35PFC configuration:priority 0 1 2 3 4 5 6 7enabled 0 0 0 0 0 0 0 0
```

启动Priority 4并确认结果:

```
# mlnx_qos -i eth35 --pfc 0,0,0,0,1,0,0,0PFC configuration:priority 0 1 2 3 4 5 6 7enabled 0 0 0 0 1 0 0 0
```



运行tc_wrap命令来验证UP（优先级）4是否被映射到VLAN。

```
# tc_wrap.py -i eth35UP 0skprio: 0skprio: 1skprio: 2 (tos: 8)skprio: 3skprio: 4 (tos: 24)skprio: 5skprio: 6 (tos: 16)skprio: 7skprio: 8skprio: 9skprio: 10skprio: 11skprio: 12skprio: 13skprio: 14skprio: 15UP 1UP 2UP 3UP 4skprio: 0 (vlan 100)skprio: 1 (vlan 100)skprio: 2 (vlan 100 tos: 8)skprio: 3 (vlan 100)skprio: 4 (vlan 100 tos: 24)skprio: 5 (vlan 100)skprio: 6 (vlan 100 tos: 16)skprio: 7 (vlan 100)UP 5UP 6UP 7
```

查看cli输出段22-30，UP（优先级）4被映射到vlan 100。



截止到目前，只有通过内核的流量才会被设置为优先级4。RDMA over Converged Ethernet（RoCE）流量不会被设置，因为它绕过了内核。



接下来，设置Egress Mapping on Kernel Bypass Traffic (RoCE)



使用 tc_wrap 命令来设置所需的优先级。在本例中，我们将所有skprio(kernel priority) 映射到L2 priority 4。

```
# tc_wrap.py -i eth35 -u 4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4UP 0UP 1UP 2UP 3UP 4skprio: 0skprio: 1skprio: 2 (tos: 8)skprio: 3skprio: 4 (tos: 24)skprio: 5skprio: 6 (tos: 16)skprio: 7skprio: 8skprio: 9skprio: 10skprio: 11skprio: 12skprio: 13skprio: 14skprio: 15skprio: 0 (vlan 100)skprio: 1 (vlan 100)skprio: 2 (vlan 100 tos: 8)skprio: 3 (vlan 100)skprio: 4 (vlan 100 tos: 24)skprio: 5 (vlan 100)skprio: 6 (vlan 100 tos: 16)skprio: 7 (vlan 100)UP 5UP 6UP 7[root@mti-mar-s6 qos]#
```

关注上面7-22行，我们看到所有skprio(kernel priority) 从UP 0调到了UP4.



**ECN**

ECN:（ExplicitCongestion Notification，显式拥塞通知）。是在交换机出口发起的拥塞机制。如下图所示，当交换机的出口buffer达到设定的阈值时，交换机会改变数据包头中的ECN位来给数据打上ECN标签。当带ECN标签的数据包到接收端后，接收端会产生CNP(Congestion NotificationPacket ),并把它发给发送端，CNP包含了导致拥塞的flow或QP信息，当接收端收到CNP后，会采取措施降低发送速度。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVq2qGD6CQrJ9NGAJF0zn8Ticu3EgFMPIvZYejowNia2NCpv0PmSNkdqKSX776H0JeXwjBUomicEEqow/640?wx_fmt=png)



在介绍了PFC和ECN两项拥塞技术的基本实现后，我们看看网络包，看看对应的标记位在哪。





**24.QoS分类的实践: RoCE的实战系列2**

**字节&位的基本概念**

正式开始之前，先复习最基础的概念，否则后文计量单位来回切换，很容易搞混：

Byte是计算机信息技术用于计量存储容量的一种计量单位。

1Byte/byte/字节=8个Bit/bit/位

1个Bit/bit/位=1个二进制数字1/0





在介绍了PFC和ECN两项拥塞技术的基本实现后，我们看看网络包，看看对应的标记位在哪。



我们先看一下报文在各层的表现形式：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUWVMViaDZWQu9rNPcxDQmUfbj8edEBa2fboNBaOZz9GABCvcLgXUBlfQ/640?wx_fmt=png)

如下图所示，报文在不同层有自己的名称。传输层是段、网络层是包、数据链路层是帧、物理层是比特。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUUXI7nrbUspicT2WzqcoKKqDIkvxEYicZu1ofrkazsVYhX3DGw6ECKXwQ/640?wx_fmt=png)

如上图所示，IP头部实在网络层被添加的。



**IPv4报文**

我们看一下IPv4报文。分为首部/报头和数据部分。IP报头大小为固定20字节（20Byte*8=160bit），总共由12部分组成。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUaiaGvcP2licKkXHZTrMcnvLpMT59WcX5JoKHbXtzgPxia4qphT0SYpaIg/640?wx_fmt=png)

我们看一下IPv4报文的各个部分：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUp6NfWTKYUXng7pibuaJEBFLlLs5A89icH6ibQ3JJ9JpG2sU7icyWGqhHfg/640?wx_fmt=png)



而ECN就位于IPv4报文中的服务类型/区分服务，简称ToS，即Type of Service（8位）中。ToS占用一个字节。其中DSCP占用6位，ECN占用2位。

- 00 ：发送主机不支持 ECN
- 01 或者 10 ：发送主机支持 ECN
- 11 ：路由器正在经历拥塞



一个支持 ECN 的主机发送数据包时将 ECN 设置为 01 或者 10 。对于支持 ECN 的主机发送的包，如果路径上的路由器支持 ECN 并且经历拥塞，它将 ECN 域设置为 11 。如果该数值已经被设置为 11 ，那么下游路径上的路由器不会修改该值。





同属于IPv4报文服务类型中的、在ECN旁边的DSCP（6位），属于QoS协议。这个我们后面讲。



**阻塞协议DCQCN**

先不着着急进行ECN配置。我们看第三种阻塞协议：DCQCN。

DC-QCN，我们先看看QCN：Quantized CongestionNotification，量化拥塞通知。



QCN为以太网提供了拥塞控制。**QCN在二层以太网络上制定，并且是针对硬件实现的**。QCN适用所有的以太网帧和所有的传输，并且主机网卡端和交换机端的行为也在标准中详细规定。QCN的配置和信息提取可以适用mlnx_qcn命令。

https://docs.mellanox.com/pages/viewpage.action?pageId=19798087



DC-QCN算法是基于数据中心TCP(DCTCP)和QCN算法的结合。所以DCQCN依赖于ECN。

注：**DCTCP作者发现TCP协议造成了数据中心网络中短数据流的高时延，其深层原因是TCP对交换机缓存空间的消耗过大，导致长数据流（的大数据量）塞满了交换机的缓存，短数据流被迫排队等待。作者设计了DCTCP：面向数据中心的TCP协议来解决上述问题。DCTCP只需要修改30行TCP代码、1个交换机参数，因此实现难度很低。DCTCP利用了交换机中新出现的显式拥塞通知（ECN）功能，将之与数据源端的控制策略相结合，从而保证交换机缓存空间的数据占据率始终低于某个阈值，这样短数据流就无需排队通过交换机，而长数据流的吞吐量同时较高。****【局限性】DCTCP利用了数据中心网的特殊属性，它并不期望应用到普通的广域网中（那里仍然是TCP的舞台）。此外，DCTCP利用了交换机中新出现的显式拥塞通知（ECN）功能，如果交换机不够新（在很多发展中或欠发达国家）那就没办法了。**



**QoS协议**

在介绍完了三项拥塞协议PFC、ECN、QCQCN后，接下来我们介绍QoS协议。

QoS协议主要有两种：

PCP（+DEI）、DSCP。



我们先看一下PCP（Priority Control Point）和DSCP（ Differentiated Serviced Code Point）在IPv4报文的位置。



DSCP在ECN的左边，占用6位，如下图所示：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUZylM4wnkGR2O4jKWibgk9z4AvL7btYRnElh49LFtMOLZscV8qnSnbRg/640?wx_fmt=png)

没看到PCP？

因为DSCP和PCP是在同一个字段的两个不同的优先级定义（复用）。如下图所示，PCP和DSCP属于不同的RFC协议，PCP占用三位。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUIMw0AfmJsicH2xs4iaGABuoaibOiclpTN0QIiciaa7a4yRaA50fd3YTY6ZEA/640?wx_fmt=png)



PCP (Priority Control Point)：3位大小的优先级，即0~7(从低到高),一共8个优先级，7的优先级最高。当交换机/路由器发生传输拥塞时，优先发送优先级高的数据帧，也就是优先级位7的帧。



与PCP相比，DSCP占用6位，因此优先级是0-63。



实际上在硬件驱动中，IP头部的ToS字段(8bit)会直接被赋值为traffic_class，而DSCP只是ToS字节中的高6位（值0~63）。



**DSCP、PCP、TC优先级映射**

查询mellonx网卡驱动 DSCP（值0~63）和PCP Priority（值0~7）和TC的映射关系：

 DSCP-->PCP Priority-->TC（硬件驱动定义）



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUt7bqbRPPQ2F4vUiaA29yibxg2NH3JawibyrBvBZbztGdr19AibV9EjAv7A/640?wx_fmt=png)



在RoCE中，应用通过rdma_set_optin函数来设置ToS值，实际上就是和TC相对应。在硬件驱动中，根据设置的ToS到DSCP值的映射表，将ToS转换成DSCP值。



最终根据DSCP值到TC的映射表来将网络流映射到对应的TC上。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUKTD6PRFwk0icVQueza4RVZaA9iaXn0y4yG1aT1n62BBCdxzzO6JMhevg/640?wx_fmt=png)

映射完成之后硬件是怎么针对优先级对网络流进行调度的呢？

 

根据应用对网络流设置的优先级，最终将网络流映射到不同的TC上，而这些TC可以人为配置调度策略，网卡根据不同的调度策略来从不同的TC中向链路上发送数据。

 

一个流量类(TC)可以被赋予不同的服务质量属性，分别有：

-  严格优先级(Strict Priority)
- 最小带宽保证(Enhanced TransmissionSelection, ETS)
- 速率限制(Rate Limit)



1. 严格优先级具有严格优先级的TC比其他非严格优先级的流具有更高的优先级，在同是严格优先级的TC中，数字越大优先级越高**（值0-7, 7最高）**。网卡总是先服务高优先级TC**（值0-7, 7最高）**，仅当最高优先级的TC没有数据传输时才会去服务下一个最高优先级TC。使用严格优先级TC可以改善对于低延迟低带宽的网络流，但是不适合传输巨型数据，因为会使得系统中其他的传输者饥饿。
2. 最小带宽保证(Enhanced Transmission Selection增强传输选择, ETS)。ETS利用提供给一个特定的流量类负载小于它的最小分配的带宽时剩余的时间周期，将这个可用的剩余时间差提供给其它流量类。**服务完严格优先级的TCs之后，链路上剩余的带宽会根据各自最小带宽保证比例分配给其它的TC。**
3. 速率限制对一个TC定义了一个最大带宽值，这与ETS不同。









**上文提到了DEI，DEI是什么？**

DEI的全称：**Drop eligible indicator** A 1-bit field. (formerly CFI[b])May be used separately or in conjunction with PCP to indicate frames eligibleto be dropped in the presence of congestion.



一个1位的字段。可以单独使用或与PCP一起使用，以表明在拥堵情况下有资格被丢弃的帧。DEI属于vLAN tag，而vLAN tag属于二层包头。



如下图所示，当三层网络包到二层数据链路层时，会增加链路层首部。vLAN标记就在数据链路层首部/帧首部：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUpuibXFfFrxZKF4J2TL3qbRMsibAoDJ3tUjsXicvM1Lfuxr6LbRFnXzsZg/640?wx_fmt=png)



以太网帧整体结构如下：

图自：https://www.cnblogs.com/33debug/p/7352373.html



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUH82c7W47y1eh9w6r00v63ibaKgeot90jcErdqrLvznxGrwTo3JGkDZg/640?wx_fmt=png)



针对以太网帧对vLAN封装，基在上图源地址和类型之间增加4个字节的802。1Q的tag，这4个字节的tag包含TPID、Priority、CFI、VLAN ID四部分：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUJmrFVkXcIib2NOjJ8ek9BFOtJP9tqnGrVxqJhuzrsmRSLah6RgPdibeA/640?wx_fmt=png)

 

其中一位的CFI就是DEI的前身：



| 字段 | 长度  | 含义                                                         | 取值                                                         |
| ---- | ----- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| TPID | 2Byte | Tag Protocol Identifier（标签协议标识符），表示数据帧类型。  | 取值为0x8100时表示IEEE 802.1Q的VLAN数据帧。如果不支持802.1Q的设备收到这样的帧，会将其丢弃。各设备厂商可以自定义该字段的值。当邻居设备将TPID值配置为非0x8100时， 为了能够识别这样的报文，实现互通，必须在本设备上修改TPID值，确保和邻居设备的TPID值配置一致。 |
| PRI  | 3bit  | Priority，表示数据帧的802.1p优先级。                         | 取值范围为0～7，值越大优先级越高。当网络阻塞时，交换机优先发送优先级高的数据帧。 |
| CFI  | 1bit  | Canonical Format Indicator（标准格式指示位），表示MAC地址在不同的传输介质中是否以标准格式进行封装，用于兼容以太网和令牌环网。 | CFI取值为0表示MAC地址以标准格式进行封装，为1表示以非标准格式封装。在以太网中，CFI的值为0。 |
| VID  | 12bit | VLAN ID，表示该数据帧所属VLAN的编号。                        | VLAN ID取值范围是0～4095。由于0和4095为协议保留取值，所以VLAN ID的有效取值范围是1～4094。 |



我们现在的图，即将PRI换成了PCP、将CFI换成了DEI。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUvS3NPBia9eOTnibiaI29vQFRU3Xo2yHVTxhrAtre3RfQn8bwgPNibu29mw/640?wx_fmt=png)

 

截止到目前，我们把DEI介绍清楚了。



那么，又有一个问题来了：我们观察到PCP在三层IP报文头和在二层帧头都有。如上图的位置，和下图的位置：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUgNjlS9bf4bU5EdYnRZ3NplATZ5bribiaejcSYAkNias8802ajFW1IzOCA/640?wx_fmt=png)

那么，到底以哪个为准呢？



**QoS分类级别**

我们看一看QoS Classification (Trust)配置，就清楚了。



https://community.mellanox.com/s/article/understanding-qos-classification--trust--on-spectrum-switches



QoS classification depends on the port configuration for QoS **trust** types. The trust level determines which packet header fields derive the **switch-priority and color.**

**QoS classification决定了哪些数据包头字段会衍生出\**switch-priority和color\**。**

There are 4 trust configuration types:

- Trust Port - The switch will use the port default settings (which means that all traffic will receive the same switch priority).

  交换机将使用端口的默认设置（这意味着所有流量将获得相同的交换机优先级）。

- Trust Layer-2 (L2) - Trust the **PCP** and **DEI** bits on the VLAN header. 信任VLAN头的PCP和DEI位。

  - In case the packet had VLAN header, based on packet **PCP** and **DEI** bits, the packet will be mapped to the configured switch priority.**如果数据包有VLAN头，根据数据包PCP和DEI位，数据包将被映射到配置的交换机优先级。**
  - Else (no VLAN), the packet will be mapped according to the default port priority settings.**否则（无VLAN），数据包将根据默认的端口优先级设置进行映射。**

- Trust Layer-3 (L3) - Trust the **DSCP** bits in the IP header。信任相信IP头中的DSCP位

  - In case of an IP header, the packet will be mapped to the switch priority according to the **DSCP** bits in the IP header. **如果是IP头，数据包将根据IP头中的DSCP位被映射到交换机优先级。**
  - Else (no IP header), the packet will be mapped according to the default port priority settings. **否则（无IP头），数据包将根据默认的端口优先级设置进行映射。**

- Trust Both (both L2 and L3)

  - Based on packet DSCP for IP packet。**基于IP数据包的DSCP**
  - else, based on packet PCP and DEI for VLAN tagged packets。 **基于数据包PCP和VLAN标记数据包的DEI。**
  - else, based on the port default setting **否则，根据端口默认设置**

注：上面这段英文出现了两个词（红色字体）： **switch-priority**和**color.**


 **switch-priority**和生成树协议STP有关。具体参考：

https://www.jannet.hk/spanning-tree-protocol-stp-zh-hant/



简单来说，Trust Layer-2 (L2) ，基于PCP和EI决定交换机优先级。Trust Layer-3 (L3)，基于 **DSCP** bits决定交换机优先级。



上文提到PCP在IP头和帧头都可以设置，但DEI只能在帧头部设置。因此读取PCP是从vLAN tag中读出来的。



我们看QoS总表：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUiaf8w4IrPKic5J9YthJzwD0VXlnfvPHhEZ30QGKpsOBu3t75eUSGQX0g/640?wx_fmt=png)



## **Switch Priority与DSCP/PCP的映射关系**

IEEE defines priority value for a packet which is used in the switch for the pause flow control.IEEE定义了一个数据包的优先级值，在交换机中用于暂停流量控制。



先看从DSCP到Switch Priority

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUlod90WSicpGGmJ4esD20XAG23G8mL08BzN8bQic3jNQrTia09XoNqRBXg/640?wx_fmt=png)

再看PCP到Switch Priority

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUB2EkSfQ2t25FF9tAKqqXIJXlNXfdBWz1LB6diaqR04nzK56dURDzcKg/640?wx_fmt=png)

再看Switch Priority到IEEE优先级：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX06pibcCTcNCmvNM6f9NJmUeLf846fddwshZzEiaaw6DiaPSNBniavaAibs8SIoG4VzzqS3nNsoichSicqQ/640?wx_fmt=png)





参考链接：

https://zhuanlan.zhihu.com/p/105286403：最详细的的IP报头注释

https://blog.51cto.com/liangchaoxi/4045903

https://blog.csdn.net/u011784495/article/details/71636993

https://blog.csdn.net/kaoa000/article/details/88844420  QoS优先级映射