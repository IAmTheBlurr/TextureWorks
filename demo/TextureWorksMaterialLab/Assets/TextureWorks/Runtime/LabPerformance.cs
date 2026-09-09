using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;

namespace TextureWorks.MaterialLab
{
    /// <summary>Explicit measurement probe shared by editor and player acceptance.</summary>
    public sealed class LabPerformance : MonoBehaviour
    {
        public string directory="Evidence/cluster";
        private IEnumerator Start()
        {
            yield return Measure(FindAnyObjectByType<LabController>(),directory,"editor");
            Destroy(gameObject);
        }
        [Serializable] public sealed class Measurement
        {
            public string view,stage,quality;
            public int frames,gpuSamples;
            public bool gpuAvailable;
            public double frameMedianMs,frameP95Ms,cpuMedianMs,gpuMedianMs,gpuP95Ms;
        }
        [Serializable] public sealed class Report
        {
            public string environment,unity,urp,gpu,graphicsApi,conditions;
            public int width,height;
            public Measurement[] measurements;
        }
        private static double Percentile(List<double> samples,double percentile)
        {
            if(samples.Count==0) return 0;
            samples.Sort(); return samples[(int)Math.Round((samples.Count-1)*percentile)];
        }
        public static IEnumerator Measure(LabController lab,string directory,string environment)
        {
            if(lab==null) throw new InvalidOperationException("No lab to measure");
            int oldVsync=QualitySettings.vSyncCount,oldTarget=Application.targetFrameRate,oldStage=lab.selectedStage;
            bool oldInput=lab.acceptInput,oldUI=lab.showInterface,oldAnimate=lab.movingLight.animate;
            float oldPhase=lab.movingLight.phase;
            float oldCoverage=lab.coverage,oldWidth=lab.blendWidth; int oldDebug=lab.debugView,oldQuality=lab.quality;
            QualitySettings.vSyncCount=0; Application.targetFrameRate=-1;
            lab.acceptInput=false; lab.showInterface=false; lab.movingLight.animate=false; lab.movingLight.ApplyPhase(0);
            var results=new List<Measurement>(); var timings=new FrameTiming[1];
            try
            {
                foreach(int viewpoint in new[]{4,3}) foreach(int quality in new[]{0,1,2}) foreach(int stage in new[]{2,3,5})
                {
                    lab.SetView(viewpoint); lab.SetStage(stage); lab.SetClusterControls(.5f,.25f,0,quality);
                    // Warm each exercised shader variant and let timing latency drain.
                    for(int warmup=0;warmup<45;++warmup) { FrameTimingManager.CaptureFrameTimings(); yield return null; }
                    var frameTimes=new List<double>(); var cpuTimes=new List<double>(); var gpuTimes=new List<double>();
                    ulong lastTimestamp=0;
                    for(int sample=0;sample<120;++sample)
                    {
                        FrameTimingManager.CaptureFrameTimings(); yield return null;
                        frameTimes.Add(Time.unscaledDeltaTime*1000.0);
                        if(FrameTimingManager.GetLatestTimings(1,timings)>0 && timings[0].frameStartTimestamp!=lastTimestamp)
                        {
                            lastTimestamp=timings[0].frameStartTimestamp;
                            if(timings[0].cpuFrameTime>0) cpuTimes.Add(timings[0].cpuFrameTime);
                            if(timings[0].gpuFrameTime>0) gpuTimes.Add(timings[0].gpuFrameTime);
                        }
                    }
                    results.Add(new Measurement {view=viewpoint==4 ? "surface history overview" : "cabinet close",
                        stage=stage==2 ? "single material POM" : stage==3 ? "single material POM and detail" : "runtime layers and detail",quality=new[]{"low 8-24/2","balanced 16-64/4","high 32-128/6"}[quality],
                        frames=frameTimes.Count,gpuSamples=gpuTimes.Count,gpuAvailable=gpuTimes.Count>0,
                        frameMedianMs=Percentile(frameTimes,.5),frameP95Ms=Percentile(frameTimes,.95),
                        cpuMedianMs=Percentile(cpuTimes,.5),gpuMedianMs=Percentile(gpuTimes,.5),gpuP95Ms=Percentile(gpuTimes,.95)});
                }
                var report=new Report {environment=environment,unity=Application.unityVersion,urp="17.6.0",
                    gpu=SystemInfo.graphicsDeviceName,graphicsApi=SystemInfo.graphicsDeviceType.ToString(),width=Screen.width,height=Screen.height,
                    conditions="Whole rendered frame; forward URP, 4x MSAA, ACES, fixed camera/illumination, UI hidden, VSync off, uncapped; 45 warmup and 120 sampled frames per case. GPU zeros mean unavailable when gpuAvailable=false.",
                    measurements=results.ToArray()};
                Directory.CreateDirectory(directory);
                File.WriteAllText(Path.Combine(directory,environment+"-performance.json"),JsonUtility.ToJson(report,true));
                Debug.Log("TEXTUREWORKS_CLUSTER_PERFORMANCE_SAVED "+environment);
            }
            finally
            {
                QualitySettings.vSyncCount=oldVsync; Application.targetFrameRate=oldTarget;
                lab.SetView(0); lab.SetStage(oldStage); lab.SetClusterControls(oldCoverage,oldWidth,oldDebug,oldQuality);
                lab.acceptInput=oldInput; lab.showInterface=oldUI; lab.movingLight.ApplyPhase(oldPhase); lab.movingLight.animate=oldAnimate;
            }
        }
    }
}
