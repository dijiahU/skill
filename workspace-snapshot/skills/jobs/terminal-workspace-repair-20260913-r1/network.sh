# Job-local routing: keep node Docker and local model endpoints direct.
export HTTP_PROXY="${HTTPS_PROXY:-${HTTP_PROXY:-http://private-host-fb6337b4cc5a.invalid:7899}}"
export HTTPS_PROXY="$HTTP_PROXY"
export http_proxy="$HTTP_PROXY" https_proxy="$HTTPS_PROXY"
bench_pod_address="$(hostname -i | awk '{print $1}')"
export NO_PROXY="localhost,127.0.0.1,::1,${LOCAL_HOST_IP:-private-host-8acf37a3a61d.invalid},${bench_pod_address}"
export no_proxy="$NO_PROXY"
export RES_OPTIONS='ndots:1 timeout:2 attempts:2'

unset bench_pod_address
