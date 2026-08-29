# GPU Workloads

Scheduling and resource management for GPU-accelerated workloads.

---

## GPU Resource Requests

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod
spec:
  containers:
  - name: gpu-container
    image: nvidia/cuda:12.0-base
    resources:
      limits:
        nvidia.com/gpu: 1      # Request 1 GPU
```

**Note**: GPU is a limit-only resource. Requests are not used for GPU.

---

## Complete GPU Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ml-inference
  labels:
    app.kubernetes.io/name: ml-inference
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: ml-inference
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ml-inference
    spec:
      # Schedule on GPU nodes only
      nodeSelector:
        accelerator: nvidia-gpu

      # Tolerate GPU node taints
      tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule

      containers:
      - name: inference
        image: ml-model:v1.0.0
        resources:
          limits:
            nvidia.com/gpu: 1
            cpu: "4"
            memory: "16Gi"
          requests:
            cpu: "2"
            memory: "8Gi"

        # GPU containers often need more startup time
        startupProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          failureThreshold: 60   # 10 minutes for model loading

        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          periodSeconds: 30

        # Volume for model caching
        volumeMounts:
        - name: model-cache
          mountPath: /models

      volumes:
      - name: model-cache
        persistentVolumeClaim:
          claimName: model-cache-pvc
```

---

## Node Affinity for GPU Types

Select specific GPU models:

```yaml
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: nvidia.com/gpu.product
            operator: In
            values:
            - NVIDIA-A100-SXM4-40GB
            - NVIDIA-A100-SXM4-80GB
          # Or by memory
          - key: gpu.gpu-vendor.example/installed-memory
            operator: Gt
            values: ["40000"]   # 40GB+ VRAM
```

---

## Labeling GPU Nodes

```bash
# Label nodes by GPU type
kubectl label nodes gpu-node-1 accelerator=nvidia-tesla-a100
kubectl label nodes gpu-node-2 accelerator=nvidia-tesla-v100

# Label by GPU count
kubectl label nodes gpu-node-1 gpu-count=8
```

---

## Tolerations for GPU Taints

GPU nodes are often tainted to prevent non-GPU workloads:

```bash
# Taint GPU nodes
kubectl taint nodes gpu-node-1 nvidia.com/gpu=present:NoSchedule
```

```yaml
# Pod must tolerate the taint
spec:
  tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
```

---

## Multi-GPU Workloads

```yaml
spec:
  containers:
  - name: training
    image: training:v1.0.0
    resources:
      limits:
        nvidia.com/gpu: 4      # Request 4 GPUs
        cpu: "32"
        memory: "128Gi"
```

**Note**: All GPUs must be on the same node. For distributed training across nodes, use specialized frameworks (Horovod, PyTorch DDP).

---

## GPU Sharing (Time-Slicing)

Enable GPU sharing for inference workloads:

```yaml
# NVIDIA device plugin ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: nvidia-device-plugin
  namespace: kube-system
data:
  config.yaml: |
    version: v1
    sharing:
      timeSlicing:
        resources:
        - name: nvidia.com/gpu
          replicas: 4          # 4 pods share each GPU
```

Then request fractional GPU:

```yaml
resources:
  limits:
    nvidia.com/gpu: 1          # Gets 1/4 of actual GPU
```

---

## Fractional GPUs (MIG)

For A100/A30 with Multi-Instance GPU:

```yaml
resources:
  limits:
    nvidia.com/mig-1g.5gb: 1   # 1 MIG slice
    # or
    nvidia.com/mig-2g.10gb: 1
    nvidia.com/mig-3g.20gb: 1
    nvidia.com/mig-7g.40gb: 1
```

---

## GPU Job Pattern

For training jobs:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: training-job
spec:
  backoffLimit: 2
  activeDeadlineSeconds: 86400  # 24 hour timeout
  template:
    spec:
      restartPolicy: Never

      nodeSelector:
        accelerator: nvidia-a100

      tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule

      containers:
      - name: training
        image: training:v1.0.0
        command: ["python", "train.py"]
        resources:
          limits:
            nvidia.com/gpu: 8
            cpu: "64"
            memory: "256Gi"
        volumeMounts:
        - name: data
          mountPath: /data
        - name: output
          mountPath: /output

      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: training-data
      - name: output
        persistentVolumeClaim:
          claimName: training-output
```

---

## Model Serving with GPU

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: llm-server
  template:
    spec:
      nodeSelector:
        accelerator: nvidia-a100

      containers:
      - name: server
        image: vllm:v0.2.0
        ports:
        - containerPort: 8000
        resources:
          limits:
            nvidia.com/gpu: 1
            cpu: "8"
            memory: "32Gi"

        # Large model loading time
        startupProbe:
          httpGet:
            path: /health
            port: 8000
          failureThreshold: 120  # 20 minutes
          periodSeconds: 10

        # Cache models
        volumeMounts:
        - name: models
          mountPath: /root/.cache/huggingface

      volumes:
      - name: models
        persistentVolumeClaim:
          claimName: model-cache

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: model-cache
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
  storageClassName: fast-ssd
```

---

## Cloud-Specific GPU Types

### AWS EKS

```yaml
nodeSelector:
  node.kubernetes.io/instance-type: p4d.24xlarge
  # or
  karpenter.k8s.aws/instance-gpu-count: "8"
```

### GKE

```yaml
nodeSelector:
  cloud.google.com/gke-accelerator: nvidia-tesla-a100
```

### AKS

```yaml
nodeSelector:
  accelerator: nvidia
  kubernetes.azure.com/agentpool: gpupool
```

---

## Monitoring GPU Usage

```bash
# Check GPU allocation
kubectl describe nodes | grep -A 5 "Allocated resources"

# NVIDIA SMI in pod
kubectl exec -it gpu-pod -- nvidia-smi

# GPU metrics (requires DCGM exporter)
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1/namespaces/*/pods/*/gpu_utilization"
```
