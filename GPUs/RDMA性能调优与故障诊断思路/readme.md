**一、性能调优篇**

**1. 确认RoCE配置是否正确**

**1.1整体确认思路**

https://community.mellanox.com/s/article/recommended-network-configuration-examples-for-roce-deployment

- Lossy网络易于部署，适合小规模环境、
- Lossy with QoS适合大规模混合流量部署
- Lossless适合存储场景。

实际配置中，网卡和TOR交换机开启PFC，而汇聚与核心交换机不开PFC的semi-losses情况比较多见。

- 网卡的ECN都是默认开启的。
- VLAN需不需要打开。
- Trust模式使用DSCP





![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcbKmzGaiay9tBm8q9a1LIL1Fwe42zs5hFSJe7olf8l2QZtFspbEl384g/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39Lkrc9Jibbcw0t8lcg2o3lwbckqszoRSVxvCMVfiawZO6iaGWyM2NILQNwAzbA/640?wx_fmt=png)

三种模式中，Lossy是开箱即用，不需要额外配置。



**1.2 Lossless fabric配置：**

https://community.mellanox.com/s/article/lossless-roce-configuration-for-linux-drivers-in-dscp-based-qos-mode

```
[root@l-csi-c6420d-03 ~]# ip a1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00inet 127.0.0.1/8 scope host lovalid_lft forever preferred_lft foreverinet6 ::1/128 scope hostvalid_lft forever preferred_lft forever2: eno16: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000link/ether 50:9a:4c:80:03:4d brd ff:ff:ff:ff:ff:ffinet 10.7.159.43/22 brd 10.7.159.255 scope global dynamic noprefixroute eno16valid_lft 18293sec preferred_lft 18293secinet6 fe80::529a:4cff:fe80:34d/64 scope link noprefixroutevalid_lft forever preferred_lft forever3: ens4f0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000link/ether b8:59:9f:fe:4d:50 brd ff:ff:ff:ff:ff:ff4: ens4f1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000link/ether b8:59:9f:fe:4d:51 brd ff:ff:ff:ff:ff:ff[root@l-csi-c6420d-03 ~]#  mlnx_qos -i ens4f0  --trust dscpDCBX mode: OS controlledPriority trust state: dscpdscp2prio mapping:prio:0 dscp:07,06,05,04,03,02,01,00,prio:1 dscp:15,14,13,12,11,10,09,08,prio:2 dscp:23,22,21,20,19,18,17,16,prio:3 dscp:31,30,29,28,27,26,25,24,prio:4 dscp:39,38,37,36,35,34,33,32,prio:5 dscp:47,46,45,44,43,42,41,40,prio:6 dscp:55,54,53,52,51,50,49,48,prio:7 dscp:63,62,61,60,59,58,57,56,default priority:Receive buffer size (bytes): 262016,0,0,0,0,0,0,0,Cable len: 7PFC configuration:priority    0   1   2   3   4   5   6   7enabled     0   0   0   0   0   0   0   0buffer      0   0   0   0   0   0   0   0tc: 1 ratelimit: unlimited, tsa: vendorpriority:  0tc: 0 ratelimit: unlimited, tsa: vendorpriority:  1tc: 2 ratelimit: unlimited, tsa: vendorpriority:  2tc: 3 ratelimit: unlimited, tsa: vendorpriority:  3tc: 4 ratelimit: unlimited, tsa: vendorpriority:  4tc: 5 ratelimit: unlimited, tsa: vendorpriority:  5tc: 6 ratelimit: unlimited, tsa: vendorpriority:  6tc: 7 ratelimit: unlimited, tsa: vendorpriority:  7[root@l-csi-c6420d-03 ~]# echo 106 > /sys/class/infiniband/mlx5_0/tc/1/traffic_class[root@l-csi-c6420d-03 ~]#  cma_roce_tos -d mlx5_0 -t 106106[root@l-csi-c6420d-03 ~]# sysctl -w net.ipv4.tcp_ecn=1net.ipv4.tcp_ecn = 1[root@l-csi-c6420d-03 ~]# mlnx_qos -i ens4f0 --pfc 0,0,0,1,0,0,0,0DCBX mode: OS controlledPriority trust state: dscpdscp2prio mapping:prio:0 dscp:07,06,05,04,03,02,01,00,prio:1 dscp:15,14,13,12,11,10,09,08,prio:2 dscp:23,22,21,20,19,18,17,16,prio:3 dscp:31,30,29,28,27,26,25,24,prio:4 dscp:39,38,37,36,35,34,33,32,prio:5 dscp:47,46,45,44,43,42,41,40,prio:6 dscp:55,54,53,52,51,50,49,48,prio:7 dscp:63,62,61,60,59,58,57,56,default priority:Receive buffer size (bytes): 130944,130944,0,0,0,0,0,0,Cable len: 7PFC configuration:priority    0   1   2   3   4   5   6   7enabled     0   0   0   1   0   0   0   0buffer      0   0   0   1   0   0   0   0tc: 1 ratelimit: unlimited, tsa: vendorpriority:  0tc: 0 ratelimit: unlimited, tsa: vendorpriority:  1tc: 2 ratelimit: unlimited, tsa: vendorpriority:  2tc: 3 ratelimit: unlimited, tsa: vendorpriority:  3tc: 4 ratelimit: unlimited, tsa: vendorpriority:  4tc: 5 ratelimit: unlimited, tsa: vendorpriority:  5tc: 6 ratelimit: unlimited, tsa: vendorpriority:  6tc: 7 ratelimit: unlimited, tsa: vendorpriority:  7
```

**1.3Lossy fabric with QoS配置**

https://community.mellanox.com/s/article/roce-configuration-for-linux-drivers-in-dscp-based-qos-mode

```
[root@l-csi-c6420d-03 ~]# mlnx_qos -i ens4f1 --trust dscpDCBX mode: OS controlledPriority trust state: dscpdscp2prio mapping:        prio:0 dscp:07,06,05,04,03,02,01,00,        prio:1 dscp:15,14,13,12,11,10,09,08,        prio:2 dscp:23,22,21,20,19,18,17,16,        prio:3 dscp:31,30,29,28,27,26,25,24,        prio:4 dscp:39,38,37,36,35,34,33,32,        prio:5 dscp:47,46,45,44,43,42,41,40,        prio:6 dscp:55,54,53,52,51,50,49,48,        prio:7 dscp:63,62,61,60,59,58,57,56,default priority:Receive buffer size (bytes): 262016,0,0,0,0,0,0,0,Cable len: 7PFC configuration:        priority    0   1   2   3   4   5   6   7        enabled     0   0   0   0   0   0   0   0        buffer      0   0   0   0   0   0   0   0tc: 1 ratelimit: unlimited, tsa: vendor         priority:  0tc: 0 ratelimit: unlimited, tsa: vendor         priority:  1tc: 2 ratelimit: unlimited, tsa: vendor         priority:  2tc: 3 ratelimit: unlimited, tsa: vendor         priority:  3tc: 4 ratelimit: unlimited, tsa: vendor         priority:  4tc: 5 ratelimit: unlimited, tsa: vendor         priority:  5tc: 6 ratelimit: unlimited, tsa: vendor         priority:  6tc: 7 ratelimit: unlimited, tsa: vendor         priority:  7[root@l-csi-c6420d-03 ~]#  echo 106 > /sys/class/infiniband/mlx5_1/tc/1/traffic_class[root@l-csi-c6420d-03 ~]# cma_roce_tos -d mlx5_1 -t 106106[root@l-csi-c6420d-03 ~]#  sysctl -w net.ipv4.tcp_ecn=1net.ipv4.tcp_ecn = 1[root@l-csi-c6420d-03 ~]#
```





**2.网卡Performance tuning**

**2.1 操作系统调优，以RHEL为例。**

https://access.redhat.com/articles/1391433

**需要指出的是，Linux参数调优方面，TCP参数对RDMA没有太大作用，UDP是有的，比如UDP的buffer cache。**



网卡调优的一个很重要的目的是避免网卡丢包。

当网卡上的RX缓冲区不能被内核快速耗尽时，通常会发生掉包和超限。当网络上的数据传输速度超过内核消耗数据包的速度时，一旦网卡缓冲区满了，网卡就会丢弃进入的数据包，并增加一个丢弃计数器。在ethtool统计中可以看到相应的计数器。这里的主要标准是中断和SoftIRQs，它们响应硬件中断并接收流量，然后在net.core.netdev_budget指定的时间内轮询卡的流量。



在硬件层面观察丢包的工具是ethtool。一般来说，寻找名称为fail, miss, error, discard, buf, fifo, full 或 drop的计数器。



例如：

```
# ethtool -S eth3
     rx_errors: 0 
     tx_errors: 0 
     rx_dropped: 0 
     tx_dropped: 0 
     rx_length_errors: 0 
     rx_over_errors: 3295
     rx_crc_errors: 0 
     rx_frame_errors: 0 
     rx_fifo_errors: 3295
     rx_missed_errors: 3295
```

网卡性能分析可从一下几个方面着手：

\* The adapter firmware level 微码版本
\- Observe drops in **ethtool -S ethX** statistics 查看统计数字
\- The adapter driver level 驱动层面
\* The Linux kernel, IRQs or SoftIRQs 内核中断。如果是RDMA，中断会非常少。
\- Check **/proc/interrupts** and **/proc/net/softnet_stat 查看设备中断**
\- The protocol layers IP, TCP, or UDP 查看协议层配置
\- Use **netstat -s** and look for error counters. 查看报错。



我们查看网卡的CPU中断统计，因为开启了RDM,所以非常少。从下午我们看到每个网卡有8个优先级。如果中断较多的话，需要确保中断分布在多个CPU核心上。



```
# cat /proc/interrupts |  awk 'NR == 1'            CPU0       CPU1       CPU2       CPU3       CPU4       CPU5       CPU6       CPU7# cat /proc/interrupts |grep -i ens4f
```



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcvVsNhuxqTWHFZicKBSiawPqdYj2BIarGUbIFBapB8RhZpdafW1SEdSPw/640?wx_fmt=png)



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcibjRnAhGU86cVzQOiaU4AwBE0Yib3pVIBnUWynRsW6nozoU6slG44CK4g/640?wx_fmt=png)

使用netstat -s命令，查看error。下面的例子显示了UDP接收错误。

\# netstat -su

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcvzCuoPuZicm6kJbzD8gmNCxic5wc0Ww2CBoRa8FyhvV4L0B06Lpu7wsQ/640?wx_fmt=png)



检查一个应用程序正在使用多少个连接。
**netstat -neopa**

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcmfKAjGTISVibnqLG5UPLH2clpF7fyLZI0By7mw58HeyeJHrss7OBEaQ/640?wx_fmt=png)



一些参数调优的范例

- https://access.redhat.com/sites/default/files/attachments/20150325_network_performance_tuning.pdf
- https://www.cnblogs.com/jking10/p/5472386.html

```
如下配置是写在sysctl.conf中，可使用sysctl -p生效，相关参数仅供参考，具体数值还需要根据机器性能，应用场景等实际情况来做更细微调整。net.core.netdev_max_backlog = 400000#该参数决定了，网络设备接收数据包的速率比内核处理这些包的速率快时，允许送到队列的数据包的最大数目。net.core.optmem_max = 10000000#该参数指定了每个套接字所允许的最大缓冲区的大小net.core.rmem_default = 10000000#指定了接收套接字缓冲区大小的缺省值（以字节为单位）。net.core.rmem_max = 10000000#指定了接收套接字缓冲区大小的最大值（以字节为单位）。net.core.somaxconn = 100000#Linux kernel参数，表示socket监听的backlog(监听队列)上限net.core.wmem_default = 11059200#定义默认的发送窗口大小；对于更大的 BDP 来说，这个大小也应该更大。net.core.wmem_max = 11059200#定义发送窗口的最大大小；对于更大的 BDP 来说，这个大小也应该更大。net.ipv4.conf.all.rp_filter = 1net.ipv4.conf.default.rp_filter = 1#严谨模式 1 (推荐)#松散模式 0net.ipv4.tcp_congestion_control = bic#默认推荐设置是 htcpnet.ipv4.tcp_window_scaling = 0#关闭tcp_window_scaling#启用 RFC 1323 定义的 window scaling；要支持超过 64KB 的窗口，必须启用该值。net.ipv4.tcp_ecn = 0#把TCP的直接拥塞通告(tcp_ecn)关掉net.ipv4.tcp_sack = 1#关闭tcp_sack#启用有选择的应答（Selective Acknowledgment），#这可以通过有选择地应答乱序接收到的报文来提高性能（这样可以让发送者只发送丢失的报文段）；#（对于广域网通信来说）这个选项应该启用，但是这会增加对 CPU 的占用。net.ipv4.tcp_max_tw_buckets = 10000#表示系统同时保持TIME_WAIT套接字的最大数量net.ipv4.tcp_max_syn_backlog = 8192#表示SYN队列长度，默认1024，改成8192，可以容纳更多等待连接的网络连接数。net.ipv4.tcp_syncookies = 1#表示开启SYN Cookies。当出现SYN等待队列溢出时，启用cookies来处理，可防范少量SYN攻击，默认为0，表示关闭；net.ipv4.tcp_timestamps = 1#开启TCP时间戳#以一种比重发超时更精确的方法（请参阅 RFC 1323）来启用对 RTT 的计算；为了实现更好的性能应该启用这个选项。net.ipv4.tcp_tw_reuse = 1#表示开启重用。允许将TIME-WAIT sockets重新用于新的TCP连接，默认为0，表示关闭；net.ipv4.tcp_tw_recycle = 1#表示开启TCP连接中TIME-WAIT sockets的快速回收，默认为0，表示关闭。net.ipv4.tcp_fin_timeout = 10#表示如果套接字由本端要求关闭，这个参数决定了它保持在FIN-WAIT-2状态的时间。net.ipv4.tcp_keepalive_time = 1800#表示当keepalive起用的时候，TCP发送keepalive消息的频度。缺省是2小时，改为30分钟。net.ipv4.tcp_keepalive_probes = 3#如果对方不予应答，探测包的发送次数net.ipv4.tcp_keepalive_intvl = 15#keepalive探测包的发送间隔net.ipv4.tcp_mem#确定 TCP 栈应该如何反映内存使用；每个值的单位都是内存页（通常是 4KB）。#第一个值是内存使用的下限。#第二个值是内存压力模式开始对缓冲区使用应用压力的上限。#第三个值是内存上限。在这个层次上可以将报文丢弃，从而减少对内存的使用。对于较大的 BDP 可以增大这些值（但是要记住，其单位是内存页，而不是字节）。net.ipv4.tcp_rmem#与 tcp_wmem 类似，不过它表示的是为自动调优所使用的接收缓冲区的值。net.ipv4.tcp_wmem = 30000000 30000000 30000000#为自动调优定义每个 socket 使用的内存。#第一个值是为 socket 的发送缓冲区分配的最少字节数。#第二个值是默认值（该值会被 wmem_default 覆盖），缓冲区在系统负载不重的情况下可以增长到这个值。#第三个值是发送缓冲区空间的最大字节数（该值会被 wmem_max 覆盖）。net.ipv4.ip_local_port_range = 1024 65000#表示用于向外连接的端口范围。缺省情况下很小：32768到61000，改为1024到65000。net.ipv4.netfilter.ip_conntrack_max=204800#设置系统对最大跟踪的TCP连接数的限制net.ipv4.tcp_slow_start_after_idle = 0#关闭tcp的连接传输的慢启动，即先休止一段时间，再初始化拥塞窗口。net.ipv4.route.gc_timeout = 100#路由缓存刷新频率，当一个路由失败后多长时间跳到另一个路由，默认是300。net.ipv4.tcp_syn_retries = 1#在内核放弃建立连接之前发送SYN包的数量。net.ipv4.icmp_echo_ignore_broadcasts = 1# 避免放大攻击net.ipv4.icmp_ignore_bogus_error_responses = 1# 开启恶意icmp错误消息保护net.inet.udp.checksum=1#防止不正确的udp包的攻击net.ipv4.conf.default.accept_source_route = 0#是否接受含有源路由信息的ip包。参数值为布尔值，1表示接受，0表示不接受。#在充当网关的linux主机上缺省值为1，在一般的linux主机上缺省值为0。#从安全性角度出发，建议你关闭该功能。net.ipv4.tcp_sack = 0#启用或关闭有选择的应答（Selective Acknowledgment），#这可以通过有选择地应答乱序接收到的报文来提高性能（这样可以让发送者只发送丢失的报文段）；#（对于广域网通信来说）这个选项应该启用，但是这会增加对 CPU 的占用。
```



**2.2 最佳实践的BIOS设置**

通用准则如下：

https://community.mellanox.com/s/article/understanding-bios-configuration-for-performance-tuning

1. **Power** - Configure power to run at maximum power for maximum performance.

 使其以最大功率运行以获得最大性能。

2. **P-State** - if enabled, the CPU (all cores on specific NUMA) will go to "sleep" mode in case there is no activity. This mode is similar to C-State but for the whole NUMA node. In most cases, it saves power in idle times. However, for performance oriented systems, when power consumption is not an issue, it is recommended that P-State is disabled.

如果启用，CPU（特定NUMA上的所有内核）将在没有活动的情况下进入 "睡眠 "模式。这种模式类似于C-状态，但适用于整个NUMA节点。在大多数情况下，它可以在空闲时节省电力。然而，对于以性能为导向的系统，当功耗不是一个问题时，建议禁用P-State。

 

3. **C-State** - For energy saving, It is possible to lower the CPU power when it is idle. Each CPU has several power modes called “C-states” or “C-modes.” This operation is not suitable while BIOS performance configuration, therefore, it should be disabled. For more information about C-State, please refer to Everything You Need to Know About the CPU C-States.

可以在CPU空闲时降低其功率。每个CPU都有几种电源模式，称为 "C-state "或 "C-modes"。这种操作不适合在BIOS性能配置时使用，因此，应该禁用它。

4. **Turbo Mode** - (Intel) Turbo Boost Technology automatically runs the processor core faster than the noted frequency. The processor must be working in the power, temperature, and specification limits of the thermal design power (TDP). Both single and multi-threaded application performance is increased. For more info, see Intel® Turbo Boost Technology Frequently Asked Questions

 会自动使处理器核心的运行速度超过指定的频率。处理器必须在热设计功率（TDP）的功率、温度和规格限制下工作。单线程和多线程的应用性能都会提高。



5. **Hyper Threading** - Allows a CPU to work on multiple streams of data simultaneously, improving performance and efficiency. In some cases, turning HyperThreading off results in higher performance with single-threaded tasks. For regular systems, in most cases, it should be turned on. In cases where the CPU is close to 100% utilization, hyper-threading might not help and even harm performance. Therefore, in such cases, Hyper Threading should be disabled.

 

允许CPU同时处理多个数据流，提高性能和效率。在某些情况下，关闭超线程会使单线程任务的性能更高。对于常规系统，在大多数情况下，应该打开。在CPU的利用率接近100%的情况下，超线程可能无济于事，甚至会损害性能。因此，在这种情况下，超线程应该被禁用。

**我在进行Iperf测试时，发现开始超线程的效果更好。**



6. **IO Non Posted Prefetching** - This parameter is relevant to haswell/broadwell and onwards, and should be disabled on those systems. Note, it is not exposed on all BIOS versions.



 这个参数与haswell/broadwell及以后的系统有关，在这些系统上应该被禁用。注意，它并不是在所有的BIOS版本上都能看到。



7. **CPU Frequency** - maximum speed for maximum performance.

 最大速度，以获得最高性能。

8. **Memory Speed** - maximum speed for maximum performance.

 内存速度 - 最大速度以获得最大性能。

9. **Memory channel mode** - Use the **independent** mode for performance. By using this mode, it is therefore possible that each memory channel has its own memory controller which operates the memory channel at full speed.

 使用 **independent**模式以获得性能。因此，通过使用这种模式，可以使每个内存通道有自己的内存控制器，以全速运行内存通道。

10. **Node Interleaving** - When node interleaving is disabled, NUMA mode is enabled. Conversely, enabling Node Interleaving means that memory is interleaved between memory nodes, and there is no NUMA presentation to the operating system. For performance reasons, we wish to disable interleaving (and enable NUMA), thus ensuring that memory is always allocated to the local NUMA node for any given logical processor.

 出于性能方面的考虑，我们希望禁用**Node Interleaving**并启用NUMA，从而确保内存总是分配给任何给定逻辑处理器的本地NUMA节点。

11. **Channel Interleaving** - Channel interleaving splits the RAM into sections to enable multiple r/w at the same time.

 **Channel Interleaving** 将RAM分割成若干部分，以便在同一时间实现多个r/w。



12. **Thermal Mode** - Functions properly in Performance mode (which also may mean high power, higher fan speed, etc.).

 在Performance mode下启动



13. **HPC Optimizations** - This mode is similar to C-state mode as they are supported in AMD processors only.

这个模式类似于C-state模式，因只在AMD处理器中支持。



 DELL服务器上设置范例：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39Lkrc6FeXZBSibSjhcr44vE3n2Zj01oJIP1C1X3o2oDdcItbDxD2XMr0RToQ/640?wx_fmt=png)



在Linux中查看CPU主频：

```
[root@l-csi-c6420d-06 ~]# cat /proc/cpuinfo | grep "MHz"cpu MHz         : 3700.000cpu MHz         : 3700.000cpu MHz         : 3700.000cpu MHz         : 3700.000cpu MHz         : 2397.148cpu MHz         : 3700.000cpu MHz         : 1228.063cpu MHz         : 3700.000
```





https://community.mellanox.com/s/article/how-to-check-cpu-core-frequency

```
[root@l-csi-c6420d-06 ~]#  cat /sys/devices/system/cpu/cpu*/cpufreq/cpuinfo_max_freq37000003700000370000037000003700000370000037000003700000[root@l-csi-c6420d-06 ~]#  cat /sys/devices/system/cpu/cpu*/cpufreq/cpuinfo_min_freq12000001200000120000012000001200000120000012000001200000
```



**2.3 网卡工具调优**

使用mlnx_tune -p指定profile进行调优。

```
[root@l-csi-c6420d-03 ~]# mlnx_tune -hUsage: mlnx_tune [options]Options:  -h, --help            show this help message and exit  -d, --debug_info      dump system debug information without setting a                        profile  -r, --report          Report HW/SW status and issues without setting a                        profile  -c, --colored         Switch using colored/monochromed status reports. Only                        applicable with --report  -p PROFILE, --profile=PROFILESet profile and run it. choose from:                        ['HIGH_THROUGHPUT','IP_FORWARDING_MULTI_STREAM_THROUGHPUT','IP_FORWARDING_MULTI_STREAM_PACKET_RATE','IP_FORWARDING_MULTI_STREAM_0_LOSS','IP_FORWARDING_SINGLE_STREAM','IP_FORWARDING_SINGLE_STREAM_0_LOSS','IP_FORWARDING_SINGLE_STREAM_SINGLE_PORT','LOW_LATENCY_VMA', 'MULTICAST']  -q, --verbosity       print debug information to the screen [default False]  -v, --version         print tool version and exit [default False]  -i INFO_FILE_PATH, --info_file_path=INFO_FILE_PATH                        info_file path. [default %s]  -l, --list_os         List supported OS [default False][root@l-csi-c6420d-03 ~]# mlnx_tune --profile=HIGH_THROUGHPUT2021-12-27 11:43:04,561 INFO Collecting node information2021-12-27 11:43:04,561 INFO Collecting OS information2021-12-27 11:43:04,565 WARNING Unknown OS [Linux,4.18.0-348.2.1.el8_5.x86_64,('centos', '8.5.2111', '')]. Tuning might be non-optimized.2021-12-27 11:43:04,565 INFO Collecting cpupower information2021-12-27 11:43:04,567 WARNING Failed to run cmd: ls -l /etc/init.d/cpupower2021-12-27 11:43:04,567 WARNING Unable to check service cpupower existence2021-12-27 11:43:04,567 INFO Collecting watchdog informationMellanox Technologies - System ReportOperation System StatusUNKNOWN4.18.0-348.2.1.el8_5.x86_64CPU StatusGenuineIntel Intel(R) Xeon(R) Gold 5122 CPU @ 3.60GHz SkylakeWarning: Frequency 3700.0MHzMemory StatusTotal: 62.18 GBFree: 56.28 GBHugepages StatusOn NUMA 1: 2048KB: 1024 pagesTransparent enabled: alwaysTransparent defrag: madviseHyper Threading StatusINACTIVEIRQ Balancer StatusNOT PRESENTFirewall StatusNOT PRESENTIP table StatusNOT PRESENTIPv6 table StatusNOT PRESENTDriver StatusOK: MLNX_OFED_LINUX-5.5-1.0.3.2 (OFED-5.5-1.0.3)ConnectX-5EX Device Status on PCI 5e:00.0FW version 16.32.1010OK: PCI Width x16Warning: PCI Speed 8GT/s >>> PCI width status is below PCI capabilities. Check PCI configuration in BIOS.PCI Max Payload Size 256PCI Max Read Request 512Local CPUs list [0, 2, 4, 6]ens4f0 (Port 1) StatusLink Type ethOK: Link status UpSpeed 100GbEMTU 1500OK: TX nocache copy 'off'ConnectX-5EX Device Status on PCI 5e:00.1FW version 16.32.1010OK: PCI Width x16Warning: PCI Speed 8GT/s >>> PCI width status is below PCI capabilities. Check PCI configuration in BIOS.PCI Max Payload Size 256PCI Max Read Request 512Local CPUs list [0, 2, 4, 6]ens4f1 (Port 1) StatusLink Type ethOK: Link status UpSpeed 100GbEMTU 1500OK: TX nocache copy 'off'2021-12-27 11:43:08,621 INFO System info file: /tmp/mlnx_tune_211227_114303.log
```

**2.4 NUMA配置**

https://community.mellanox.com/s/article/understanding-numa-node-for-performance-benchmarks



[root@l-csi-c6420d-06 ~]# lscpu |grep "NUMA node"

NUMA node(s):    2

NUMA node0 CPU(s):  0,2,4,6,8,10,12,14

NUMA node1 CPU(s):  1,3,5,7,9,11,13,15



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39Lkrc6TSUrDhRvOoHEsaoo6lQy9KqZZYRMKvr854LOiaFv199J9Xiaicw6CI4Q/640?wx_fmt=png)



\#i=$(ps -ef |grep -i iperf | grep-v color |awk '{print $2}'); taskset -pc 0,2,4,6,8,10,12,14 $i&







**二、故障诊断篇**

RDMA的故障诊断大体上分为两大部分，IB层的诊断和标卡层的诊断。

我们先看IB层的诊断。

**1.IB层诊断**

**1.1.确认有无硬件和微码报错**

```
Externalsyndrome, FW assert, For example:mlx5_core0000:17:00.0: device's health compromised -reached miss countmlx5_core0000:17:00.0: assert_var[0] 0x00000001…mlx5_core0000:17:00.0: synd0x1: firmware internal errormlx5_core0000:17:00.0: ext_synd0x8da6
```

**1.2.tcpdump抓包**

具体参照：[RDMA流量抓包分析](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663510141&idx=1&sn=e941f7357b564f5ae5674803dc9a51ff&chksm=81d6b705b6a13e1314491a657a0998fb404ed74cfdd8010477e22cae1fc11f75c35f0ea76a0c&scene=21#wechat_redirect)



**1.3.RoCE完整诊断思路**

https://community.mellanox.com/s/article/RoCE-Debug-Flow-for-Linux

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcllfM3zfVglvL7JMwpibxiclVcsKK1ibfwXdSeY8KHPWO9M6Yty5L5AfnA/640?wx_fmt=png)

```
#确认RDMA linkup[root@l-csi-c6420d-03 ~]# rdma linklink mlx5_0/1 state ACTIVE physical_state LINK_UP netdev ens4f0link mlx5_1/1 state ACTIVE physical_state LINK_UP netdev ens4f1[root@l-csi-c6420d-03 ~]# ibdev2netdevmlx5_0 port 1 ==> ens4f0 (Up)mlx5_1 port 1 ==> ens4f1 (Up)[root@l-csi-c6420d-03 ~]# show_gids mlx5_0DEV     PORT    INDEX   GID                                     IPv4            VER     DEV---     ----    -----   ---                                     ------------    ---     ---mlx5_0  1       0       fe80:0000:0000:0000:ba59:9fff:fefe:4d50                 v1      ens4f0mlx5_0  1       1       fe80:0000:0000:0000:ba59:9fff:fefe:4d50                 v2      ens4f0mlx5_0  1       2       0000:0000:0000:0000:0000:ffff:0a07:9f47 10.7.159.71     v1      ens4f0mlx5_0  1       3       0000:0000:0000:0000:0000:ffff:0a07:9f47 10.7.159.71     v2      ens4f0n_gids_found=4[root@l-csi-c6420d-03 ~]# lspci -D | grep Mellanox0000:5e:00.0 Ethernet controller: Mellanox Technologies MT28800 Family [ConnectX-5 Ex]0000:5e:00.1 Ethernet controller: Mellanox Technologies MT28800 Family [ConnectX-5 Ex]确认RoCE已经启动[root@l-csi-c6420d-03 ~]# cat /sys/bus/pci/devices/0000\:5e\:00.0/roce_enable1[root@l-csi-c6420d-03 ~]# echo 0 > /sys/bus/pci/devices/0000\:5e\:00.0/roce_enable[root@l-csi-c6420d-03 ~]# cat /sys/bus/pci/devices/0000\:5e\:00.0/roce_enable0如果未启动，手工启动。默认是启动de 。[root@l-csi-c6420d-03 ~]# echo 1 > /sys/bus/pci/devices/0000\:5e\:00.0/roce_enable[root@l-csi-c6420d-03 ~]# cat /sys/bus/pci/devices/0000\:5e\:00.0/roce_enable1[root@l-csi-c6420d-03 ~]# ip address  show dev ens4f03: ens4f0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000link/ether b8:59:9f:fe:4d:50 brd ff:ff:ff:ff:ff:ffinet 10.7.159.71/22 brd 10.7.159.255 scope global ens4f0valid_lft forever preferred_lft foreverMTU Size 不小于1250.[root@l-csi-c6420d-03 ~]# ping -f -c 100  -s 1250 -M do  10.7.159.71PING 10.7.159.71 (10.7.159.71) 1250(1278) bytes of data.查看设备详细信息：[root@l-csi-c6420d-03 ~]# ibv_devinfo  -d mlx5_0 -vvvhca_id: mlx5_0transport:                      InfiniBand (0)fw_ver:                         16.32.1010node_guid:                      b859:9f03:00fe:4d50sys_image_guid:                 b859:9f03:00fe:4d50vendor_id:                      0x02c9vendor_part_id:                 4121hw_ver:                         0x0board_id:                       MT_0000000009phys_port_cnt:                  1max_mr_size:                    0xffffffffffffffffpage_size_cap:                  0xfffffffffffff000max_qp:                         131072max_qp_wr:                      32768device_cap_flags:               0xed721c36BAD_PKEY_CNTRBAD_QKEY_CNTRAUTO_PATH_MIGCHANGE_PHY_PORTPORT_ACTIVE_EVENTSYS_IMAGE_GUIDRC_RNR_NAK_GENMEM_WINDOWXRCMEM_MGT_EXTENSIONSMEM_WINDOW_TYPE_2BRAW_IP_CSUMMANAGED_FLOW_STEERINGUnknown flags: 0xC8400000max_sge:                        30max_sge_rd:                     30max_cq:                         16777216max_cqe:                        4194303max_mr:                         16777216max_pd:                         8388608max_qp_rd_atom:                 16max_ee_rd_atom:                 0max_res_rd_atom:                2097152max_qp_init_rd_atom:            16max_ee_init_rd_atom:            0atomic_cap:                     ATOMIC_HCA (1)max_ee:                         0max_rdd:                        0max_mw:                         16777216max_raw_ipv6_qp:                0max_raw_ethy_qp:                0max_mcast_grp:                  2097152max_mcast_qp_attach:            240max_total_mcast_qp_attach:      503316480max_ah:                         2147483647max_fmr:                        0max_srq:                        8388608max_srq_wr:                     32767max_srq_sge:                    31max_pkeys:                      128local_ca_ack_delay:             16general_odp_caps:ODP_SUPPORTODP_SUPPORT_IMPLICITrc_odp_caps:SUPPORT_SENDSUPPORT_RECVSUPPORT_WRITESUPPORT_READSUPPORT_SRQuc_odp_caps:NO SUPPORTud_odp_caps:SUPPORT_SENDxrc_odp_caps:SUPPORT_SENDSUPPORT_WRITESUPPORT_READSUPPORT_SRQcompletion timestamp_mask:                      0x7fffffffffffffffhca_core_clock:                 78125kHZraw packet caps:C-VLAN stripping offloadScatter FCS offloadIP csum offloadDelay dropdevice_cap_flags_ex:            0x30000055ED721C36RAW_SCATTER_FCSPCI_WRITE_END_PADDINGUnknown flags: 0x3000004100000000tso_caps:max_tso:                        262144supported_qp:SUPPORT_RAW_PACKETrss_caps:max_rwq_indirection_tables:                     1048576max_rwq_indirection_table_size:                 2048rx_hash_function:                               0x1rx_hash_fields_mask:                            0x800000FFsupported_qp:SUPPORT_RAW_PACKETmax_wq_type_rq:                 8388608packet_pacing_caps:qp_rate_limit_min:      1kbpsqp_rate_limit_max:      100000000kbpssupported_qp:SUPPORT_RAW_PACKETtag matching not supportedcq moderation caps:max_cq_count:   65535max_cq_period:  4095 usmaximum available device memory:        131072Bytesnum_comp_vectors:               8port:   1state:                  PORT_ACTIVE (4)max_mtu:                4096 (5)active_mtu:             1024 (3)sm_lid:                 0port_lid:               0port_lmc:               0x00link_layer:             Ethernetmax_msg_sz:             0x40000000port_cap_flags:         0x04010000port_cap_flags2:        0x0000max_vl_num:             invalid value (0)bad_pkey_cntr:          0x0qkey_viol_cntr:         0x0sm_sl:                  0pkey_tbl_len:           1gid_tbl_len:            255subnet_timeout:         0init_type_reply:        0active_width:           4X (2)active_speed:           25.0 Gbps (32)phys_state:             LINK_UP (5)GID[  0]:               fe80:0000:0000:0000:ba59:9fff:fefe:4d50, RoCE v1GID[  1]:               fe80::ba59:9fff:fefe:4d50, RoCE v2GID[  2]:               0000:0000:0000:0000:0000:ffff:0a07:9f47, RoCE v1GID[  3]:               ::ffff:10.7.159.71, RoCE v2
```

**1.4 查看IB层的counters**

https://community.mellanox.com/s/article/understanding-mlx5-linux-counters-and-status-parameters


IB层的Counter有3大目录，有不同的妙用：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcGcL74wticNrYiaxdTS1n8mr1k8QE34sMOl7ibOsQHW70cz40B9wcgTIzQ/640?wx_fmt=png)

如果做故障诊断，我们主要关注后两个目录。



目录1：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcB0C1kbT6rZPiaicbUtia15apN7LZqNpgAGIsicsqKIBrlyq0QrprnahZcw/640?wx_fmt=png)

\#cd /sys/class/infiniband/mlx5_0/ports/1/counters

[root@l-csi-c6420d-03 counters]# cat link_error_recovery

0

\#[root@l-csi-c6420d-03 counters]# cat link_downed

0

\#[root@l-csi-c6420d-03 counters]#



目录2：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcYfgs5GoynHM6W8Rp2GHicx1uk2kTicaW5hT9Zy3ZYw3LNdqAoLhjQI6g/640?wx_fmt=png)

\#cd /sys/class/infiniband/mlx5_0/ports/1/hw_counters

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcrDItgCAtJOrozX3wicGwQG8VVdCfoqYo3gcKqelpL34wOUjLtONmsPQ/640?wx_fmt=png)



目录3：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcswX2uXkv7DHWETVQudWRKcRGyOiafvyJsvJ2bNv0Nic5METibjR0ZXk3A/640?wx_fmt=png)

\# cd /sys/class/net/ens4f0/debug/

我们查看文件里的内容：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcZaGrUpMGY3iaibWtHoQp4xmg28vx9jpeOlGMicrVTcvHmTbwxnVtF8aiaA/640?wx_fmt=png)



参照：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcxVuMBicscGT8rfhicWvpM3qiaZ51lyTKhEkiblmPt7PHsKO8nLgHOIQictw/640?wx_fmt=png)

**2. 从标卡角度分析网卡故障。**



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcUQ5tsqhX9j1Iuy5BSx0uEdIAFjfCxfk5FJqQrQVy1S172yjstRISIA/640?wx_fmt=png)

更多内容参考：

[Linux网络问题诊断大全-全篇](http://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663507268&idx=1&sn=f66c5ad9a5adce2795877c83c02c49b9&chksm=81d6a23cb6a12b2a2531cf2fda6f0384ea7772f56d9abc03db502b5f0d36674012221dc75de7&scene=21#wechat_redirect)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWbQbNibIkO6fXUdPia39LkrcS8xOibaJtemp0f9KFITtibr1jI9qz3O0wibqLj2CYPppXRLpsoLvJuibzQ/640?wx_fmt=png)