# A step-by-step guide to install NVIDIA Drivers and Cuda Toolkit

https://medium.com/virtual-force-inc/a-step-by-step-guide-to-install-nvidia-drivers-and-cuda-toolkit-855c75efcdb6

A complete guide to setup GPU for ML development.

This article takes you step-by-step to enable your GPU machine for any kind of development tasks, especially for machine learning and data science.

***Why to setup GPU?\***

When you want to utilize a GPU machine for your development tasks in machine learning and data science, either you have a local GPU machine or a cloud instance e.g AWS EC2 instances. You can’t just *turn-on* your GPU machine and directly jump into development. If you are on an NVIDIA’s GPU machine, it first needs to be enabled and make it development-ready by installing NVIDIA’s Drivers and Cuda Toolkit.

***What are NVIDIA Drivers and Cuda Toolkit?\***

This article doesn’t go into much detail of what are these NVIDIA drivers and Cuda Toolkit. Instead I will give a very short description for quick understanding.

> **NVIDIA Drivers** are software packages that facilitate communication between the operating system (OS) and the NVIDIA GPU hardware. These drivers are necessary for running any application that utilizes the GPU, including video games, multimedia software, and computational tasks such as deep learning, scientific simulations, and data processing.
>
> **CUDA (Compute Unified Device Architecture) Toolkit** is a software development platform created by NVIDIA specifically for parallel computing using NVIDIA GPUs. The [CUDA Toolkit](https://developer.nvidia.com/cuda-toolkit) from NVIDIA provides everything you need to develop GPU-accelerated applications. The CUDA Toolkit includes GPU-accelerated libraries, a compiler, development tools and the CUDA runtime.

# **How to install NVIDIA Drivers and Cuda Toolkit?**

This guide is for Linux based machines with Ubuntu 22.04.
An NVIDIA card with Cuda compatibility is required as well.

> First check if NVIDIA Drivers and Cuda toolkit are already installed.
> `nvidia-smi` for checking Nvidia drivers
> `nvcc --version` for checking Cuda toolkit

If both of these or either of them not installed, follow the below steps to install.

# **1- Upgrade the Ubuntu**

```
1- sudo apt update
2- sudo apt upgrade
```

# 2- NVIDIA Drivers Installation

**Install compatible NVIDIA Driver**

Drivers can be listed through Linux commands and install the recommended driver.

Follow these commands for listing and installing driver.

1. `sudo apt install ubuntu-drivers-common`
2. `sudo ubuntu-drivers devices`
   This command will show list of all compatible drivers and recommends a driver as well.

![img](https://miro.medium.com/v2/resize:fit:1050/1*Vk0kbAvARAOACmLPWRpbqw.png)

List of NVIDIA Drivers in Ubuntu

Now run follwoing command to install the driver.

3. `sudo apt install nvidia-driver-number`

For example: `sudo apt install nvidia-driver-535`

4. Reboot the system `sudo reboot now`.
5. Now when you run command `nvidia-smi`, it will output like this:

![img](https://miro.medium.com/v2/resize:fit:1050/1*uBomo9w6aVgbK0aIcWiomw.png)

Output of nvidia-smi commng

This show that compatible Nvidia driver is successfully installed.

# 3- Cuda Toolkit Installation

> To install the cuda toolkit, first check if `gcc` is already installed.
> `gcc -v.` If `gcc` is not installed, command `sudo apt install gcc` to install it.

1. Once `gcc` is installed, go to NVIDIA's Cuda download website https://developer.nvidia.com/cuda-downloads and navigate the website step-by-step to find the right version for our system.

![img](https://miro.medium.com/v2/resize:fit:1050/1*ksMnSb5OoJsAYlfBeHl4Wg.png)

Snapshot of Cuda Toolkit’s Download Page

It will run commands like these to download and install the relevant version of toolkit.

> Check the latest commands on Nvidia’s website (https://developer.nvidia.com/cuda-downloads), incase version has been update.

```
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-ubuntu2004.pin
sudo mv cuda-ubuntu2004.pin /etc/apt/preferences.d/cuda-repository-pin-600
wget https://developer.download.nvidia.com/compute/cuda/12.3.2/local_installers/cuda-repo-ubuntu2004-12-3-local_12.3.2-545.23.08-1_amd64.deb
sudo dpkg -i cuda-repo-ubuntu2004–12–3-local_12.3.2–545.23.08–1_amd64.deb
sudo cp /var/cuda-repo-ubuntu2004–12–3-local/cuda-*-keyring.gpg /usr/share/keyrings/
sudo apt-get update
sudo apt-get -y install cuda-toolkit-12–3
```

If dependency errors occur during installation, try running `sudo apt --fix-broken install`.

2. Reboot the system `sudo reboot now`

**3. Update the Environment Setup**

- Open the .bashrc file using `nano ~/.bashrc`
- Copy and paste following lines at the end of the file.

```
export PATH=/usr/local/cuda/bin{PATH:+:{PATH}}
export LD_LIBRARY_PATH=/usr/local/cuda-12.2/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}
```

- Press `Ctrl+x`, write `y` and then press `Enter` to save the file.
- Reload the file `. ~/.bashrc`
- Confirm if Cuda toolkit got installed, `nvcc --version`. It will output like this.

![img](https://miro.medium.com/v2/resize:fit:1050/1*PGZEaDPsD3cJbuYaj49Ldw.png)

nvcc -V command output — showing Cuda Toolkit is successfully installed

> *In case Cuda is still not installed, run command* `*sudo apt install nvidia-cuda-toolkit*`*, and confirm the installation by* `*nvcc --version*`*.*