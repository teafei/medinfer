import asyncio
import platform
import shutil
import statistics
import subprocess
import time
from importlib.metadata import PackageNotFoundError, version

import psutil


def percentile(values, q):
    """Linear interpolation, equivalent to NumPy's default percentile method."""
    if not values:
        return None
    values = sorted(values)
    index = (len(values) - 1) * q
    lo = int(index)
    return values[lo] + (values[min(lo + 1, len(values) - 1)] - values[lo]) * (index - lo)


def environment():
    packages = {}
    for package in ("medinfer", "mlx", "mlx-lm", "httpx", "fastapi", "psutil"):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            pass
    return {
        "os": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "system_memory_bytes": psutil.virtual_memory().total,
        "packages": packages,
    }


class ResourceSampler:
    def __init__(self, gpu_index=None, interval_s=0.05):
        self.gpu_index, self.interval = gpu_index, interval_s
        self.rss_peak = 0
        self.gpu_peak_mib = None
        self.gpu_name = None
        self.gpu_sample_count = 0
        self.task = None
        self.gpu_available = gpu_index is not None and shutil.which("nvidia-smi") is not None

    def _gpu(self):
        try:
            out = (
                subprocess.run(
                    [
                        "nvidia-smi",
                        f"--id={self.gpu_index}",
                        "--query-gpu=name,memory.used",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1,
                    check=True,
                )
                .stdout.strip()
                .split(",")
            )
            return out[0].strip(), float(out[-1])
        except (OSError, ValueError, subprocess.SubprocessError):
            return None

    async def _sample(self):
        last_gpu = 0
        while True:
            self.rss_peak = max(self.rss_peak, psutil.Process().memory_info().rss)
            if self.gpu_available and time.monotonic() - last_gpu >= 0.5:
                sample = await asyncio.to_thread(self._gpu)
                if sample:
                    self.gpu_name, used = sample
                    self.gpu_peak_mib = max(self.gpu_peak_mib or 0, used)
                    self.gpu_sample_count += 1
                last_gpu = time.monotonic()
            await asyncio.sleep(self.interval)

    async def __aenter__(self):
        self.task = asyncio.create_task(self._sample())
        await asyncio.sleep(0)
        return self

    async def __aexit__(self, *_):
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass

    def result(self):
        return {
            "gateway_rss_peak_bytes": self.rss_peak,
            "rss_sampling_interval_s": self.interval,
            "gpu_device_memory_peak_mib": self.gpu_peak_mib,
            "gpu_name": self.gpu_name,
            "gpu_sample_count": self.gpu_sample_count,
            "gpu_scope": "local whole device, not per-model; remote GPU unobserved",
        }


def aggregate(records, wall_s):
    ok = [r for r in records if r["error"] is None]
    quality = {}
    for task in ("extraction", "qa", "summary"):
        subset = [r for r in ok if r["task"] == task]
        quality[task] = {"n_successful": len(subset)}
        for key in {k for r in subset for k in r["scores"]}:
            quality[task][key] = statistics.mean(r["scores"][key] for r in subset)
    times = [r["latency_s"] for r in ok]
    ttfts = [r["ttft_s"] for r in ok if r["ttft_s"] is not None]
    known = [r for r in ok if r["completion_tokens"] is not None]
    return {
        "requests": len(records),
        "successful": len(ok),
        "failed": len(records) - len(ok),
        "error_rate": (len(records) - len(ok)) / len(records) if records else None,
        "wall_s": wall_s,
        "throughput_requests_s": len(ok) / wall_s if wall_s else None,
        "latency_p50_s": percentile(times, 0.50),
        "latency_p95_s": percentile(times, 0.95),
        "ttft_p50_s": percentile(ttfts, 0.50),
        "ttft_p95_s": percentile(ttfts, 0.95),
        "token_count_coverage": len(known) / len(ok) if ok else None,
        "output_tokens_s": sum(r["completion_tokens"] for r in known) / wall_s
        if ok and len(known) == len(ok) and wall_s
        else None,
        "mean_request_tokens_s": statistics.mean(
            r["tokens_s"] for r in ok if r["tokens_s"] is not None
        )
        if any(r["tokens_s"] is not None for r in ok)
        else None,
        "truncated": sum(r["finish_reason"] == "length" for r in ok),
        "quality": quality,
    }
