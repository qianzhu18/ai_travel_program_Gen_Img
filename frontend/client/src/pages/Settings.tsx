import { useState, useEffect, useCallback } from "react";
import { MainLayout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import {
  Save,
  Loader2,
  Droplets,
  Expand,
  MessageSquare,
  Image,
  ScanFace,
  FileDown,
  Settings2,
  Plug,
} from "lucide-react";
import axios from "axios";
import { API } from "@/lib/apiConfig";

// ---------- types ----------
interface SettingsData {
  [key: string]: string;
}

// ---------- helpers ----------
function cv(data: SettingsData, key: string, fallback: string): string {
  return data[key] ?? fallback;
}

// ---------- component ----------
export default function Settings() {
  const [settings, setSettings] = useState<SettingsData>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingBailian, setTestingBailian] = useState(false);
  const [testingArk, setTestingArk] = useState(false);

  // fetch settings on mount
  const fetchSettings = useCallback(async () => {
    try {
      const res = await axios.get(API.settings.list);
      const raw = res.data?.data ?? res.data;
      // backend returns {key: {value, description}} — flatten to {key: value}
      const flat: SettingsData = {};
      for (const [k, v] of Object.entries(raw)) {
        flat[k] = (v as any)?.value ?? "";
      }
      setSettings(flat);
    } catch {
      toast.error("加载设置失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  // update local state
  const set = (key: string, value: string) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  // save all
  const handleSave = async () => {
    setSaving(true);
    try {
      const arkModel =
        (settings.ark_model ?? "").trim() || "doubao-seedream-4-5-251128";
      const normalized: SettingsData = {
        ...settings,
        generate_engine: "ark",
        ark_model: arkModel,
      };
      const settingsArr = Object.entries(normalized).map(([key, value]) => ({
        key,
        value: String(value),
      }));
      await axios.post(API.settings.update, { settings: settingsArr });
      toast.success("设置已保存");
    } catch {
      toast.error("保存失败");
    } finally {
      setSaving(false);
    }
  };

  // test connection
  const testConnection = async (
    service: "bailian" | "apiyi" | "ark",
    apiKey: string,
    setTesting: (v: boolean) => void,
    model?: string,
  ) => {
    if (!apiKey) {
      toast.warning("请先输入有效的 API Key");
      return;
    }
    const modelText = (model ?? "").trim();
    if (service === "ark" && !modelText) {
      toast.warning("请先填写可用的 Ark 模型 ID");
      return;
    }
    setTesting(true);
    try {
      const res = await axios.post(API.settings.testConnection, {
        service,
        api_key: apiKey,
        ...(modelText ? { model: modelText } : {}),
      });
      if (res.data?.data?.connected) {
        toast.success(res.data?.message ?? "连接成功");
      } else {
        toast.error(res.data?.message ?? "连接失败");
      }
    } catch {
      toast.error("连接测试失败");
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <MainLayout title="系统设置">
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout
      title="系统设置"
      actions={
        <Button onClick={handleSave} disabled={saving}>
          {saving ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Save className="w-4 h-4 mr-2" />
          )}
          保存设置
        </Button>
      }
    >
      <div className="max-w-4xl mx-auto space-y-6 pb-8">
        {/* ===== 1. 图片去水印配置 ===== */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Droplets className="w-5 h-5" />
              图片去水印配置
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>默认水印区域</Label>
                <Select
                  value={cv(settings, "watermark_region", "右下角")}
                  onValueChange={(v) => set("watermark_region", v)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="右下角">右下角</SelectItem>
                    <SelectItem value="左下角">左下角</SelectItem>
                    <SelectItem value="右上角">右上角</SelectItem>
                    <SelectItem value="左上角">左上角</SelectItem>
                    <SelectItem value="全图检测">全图检测</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>
                  边距比例：{cv(settings, "watermark_margin", "15")}%
                </Label>
                <Slider
                  value={[Number(cv(settings, "watermark_margin", "15"))]}
                  onValueChange={([v]) => set("watermark_margin", String(v))}
                  min={5}
                  max={30}
                  step={1}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>去水印引擎</Label>
              <Select
                value={cv(settings, "watermark_engine", "auto")}
                onValueChange={(v) => set("watermark_engine", v)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">自动（优先本地）</SelectItem>
                  <SelectItem value="iopaint">IOPaint（本地）</SelectItem>
                  <SelectItem value="volc">火山视觉（云端）</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between">
              <Label>GPU 加速</Label>
              <Switch
                checked={cv(settings, "gpu_acceleration", "1") === "1"}
                onCheckedChange={(v) =>
                  set("gpu_acceleration", v ? "1" : "0")
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>火山视觉 AccessKeyId</Label>
                <Input
                  type="password"
                  placeholder="AK..."
                  value={cv(settings, "volc_access_key_id", "")}
                  onChange={(e) => set("volc_access_key_id", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>火山视觉 SecretAccessKey</Label>
                <Input
                  type="password"
                  placeholder="SK..."
                  value={cv(settings, "volc_secret_access_key", "")}
                  onChange={(e) => set("volc_secret_access_key", e.target.value)}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ===== 2. 图片扩图配置 ===== */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Expand className="w-5 h-5" />
              图片扩图配置
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>目标比例</Label>
                <Select
                  value={cv(settings, "target_ratio", "9:16")}
                  onValueChange={(v) => set("target_ratio", v)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="9:16">9:16</SelectItem>
                    <SelectItem value="16:9">16:9</SelectItem>
                    <SelectItem value="4:3">4:3</SelectItem>
                    <SelectItem value="3:4">3:4</SelectItem>
                    <SelectItem value="1:1">1:1</SelectItem>
                    <SelectItem value="自定义">自定义</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>扩图引擎</Label>
                <Select
                  value={cv(settings, "expand_engine", "seedream")}
                  onValueChange={(v) => set("expand_engine", v)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="seedream">SeedDream 4.5</SelectItem>
                    <SelectItem value="iopaint">IOPaint（本地）</SelectItem>
                    <SelectItem value="auto">自动（优先本地）</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div className="space-y-1">
                <Label>扩图失败自动降级填充</Label>
                <p className="text-xs text-muted-foreground">
                  关闭后，扩图失败会直接报错而不是生成条纹填充图（推荐关闭以避免上下撕扯条纹）
                </p>
              </div>
              <Switch
                checked={cv(settings, "expand_allow_fallback", "1") === "1"}
                onCheckedChange={(v) => set("expand_allow_fallback", v ? "1" : "0")}
              />
            </div>
          </CardContent>
        </Card>

        {/* ===== 3. 提示词生成配置 ===== */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <MessageSquare className="w-5 h-5" />
              提示词生成配置
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>阿里百炼 API Key</Label>
              <div className="flex gap-2">
                <Input
                  type="password"
                  placeholder="输入 API Key"
                  value={cv(settings, "prompt_api_key", "")}
                  onChange={(e) => set("prompt_api_key", e.target.value)}
                  className="flex-1"
                />
                <Button
                  variant="outline"
                  size="sm"
                  disabled={testingBailian}
                  onClick={() =>
                    testConnection(
                      "bailian",
                      settings.prompt_api_key ?? "",
                      setTestingBailian,
                    )
                  }
                >
                  {testingBailian ? (
                    <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                  ) : (
                    <Plug className="w-4 h-4 mr-1" />
                  )}
                  测试连接
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label>系统 Prompt</Label>
              <Textarea
                rows={4}
                placeholder="配置大模型生成提示词的规则..."
                value={cv(settings, "prompt_system_prompt", "")}
                onChange={(e) => set("prompt_system_prompt", e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        {/* ===== 4. 图片生成引擎配置 ===== */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Image className="w-5 h-5" />
              图片生成引擎配置
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-muted-foreground">
              当前生图链路固定为：即梦 Ark 图文生图（单图输入单图输出）。
              实际使用模型取决于下方 `ark_model` 配置项（需为账号已开通模型）。
            </p>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div className="space-y-1">
                <Label>关闭生图水印</Label>
                <p className="text-xs text-muted-foreground">
                  开启后会向即梦 Ark 请求 `watermark=false`
                </p>
              </div>
              <Switch
                checked={cv(settings, "disable_generation_watermark", "1") === "1"}
                onCheckedChange={(v) => set("disable_generation_watermark", v ? "1" : "0")}
              />
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <div className="space-y-1">
                <Label>强制无水印兜底</Label>
                <p className="text-xs text-muted-foreground">
                  生图成功后会再执行一次角落去水印；若清理失败则该图判定失败，杜绝带水印出图
                </p>
              </div>
              <Switch
                checked={cv(settings, "strict_no_watermark", "1") === "1"}
                onCheckedChange={(v) => set("strict_no_watermark", v ? "1" : "0")}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              若模板页仍出现右下角 “AI generated”，通常是上游角标或去水印引擎不可用导致。
              建议同时开启“关闭生图水印 + 强制无水印兜底”，并确保去水印引擎可用。
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>默认提示词前缀</Label>
                <Input
                  placeholder="自动添加到每条提示词前面"
                  value={cv(settings, "generate_prompt_prefix", "")}
                  onChange={(e) =>
                    set("generate_prompt_prefix", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>默认提示词后缀</Label>
                <Input
                  placeholder="如：4K, high quality"
                  value={cv(settings, "generate_prompt_suffix", "")}
                  onChange={(e) =>
                    set("generate_prompt_suffix", e.target.value)
                  }
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ===== 4.5 即梦 Ark API 配置 ===== */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Image className="w-5 h-5" />
              即梦 Ark API 配置
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-muted-foreground">
              使用即梦 Ark API 进行图文生图（单图输入单图输出）。支持图像元素增删、风格转化、材质替换、色调迁移、改变背景/视角/尺寸等。
            </p>
            <div className="space-y-2">
              <Label>即梦 Ark API Key</Label>
              <div className="flex gap-2">
                <Input
                  type="password"
                  placeholder="Bearer Token..."
                  value={cv(settings, "ark_api_key", "")}
                  onChange={(e) => set("ark_api_key", e.target.value)}
                  className="flex-1"
                />
                <Button
                  variant="outline"
                  size="sm"
                  disabled={testingArk}
                  onClick={() =>
                    testConnection(
                      "ark",
                      settings.ark_api_key ?? "",
                      setTestingArk,
                      settings.ark_model ?? "doubao-seedream-4-5-251128",
                    )
                  }
                >
                  {testingArk ? (
                    <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                  ) : (
                    <Plug className="w-4 h-4 mr-1" />
                  )}
                  验证可用性
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                格式: Bearer Token（从火山方舟控制台获取）
              </p>
            </div>
            <div className="space-y-2">
              <Label>模型 ID（ark_model）</Label>
              <Input
                placeholder="例如：doubao-seedream-4-5-251128"
                value={cv(settings, "ark_model", "doubao-seedream-4-5-251128")}
                onChange={(e) => set("ark_model", e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                请填写当前账号已开通的模型 ID。点击“验证可用性”可实时检测。
              </p>
            </div>
          </CardContent>
        </Card>

        {/* ===== 5. 宽脸版本生成配置 ===== */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ScanFace className="w-5 h-5" />
              宽脸版本生成配置
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>生成引擎</Label>
              <Select
                value={cv(settings, "wideface_engine", "nanobanana")}
                onValueChange={(v) => set("wideface_engine", v)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="nanobanana">Nano Banana Pro</SelectItem>
                  <SelectItem value="seedream">SeedDream 4.5</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>宽脸生成提示词</Label>
              <Textarea
                rows={3}
                placeholder="宽脸图生成的系统提示词..."
                value={cv(settings, "wideface_prompt", "")}
                onChange={(e) => set("wideface_prompt", e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        {/* ===== 6. 画质压缩配置 ===== */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileDown className="w-5 h-5" />
              画质压缩配置
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>启用压缩</Label>
              <Switch
                checked={cv(settings, "compress_enabled", "1") === "1"}
                onCheckedChange={(v) =>
                  set("compress_enabled", v ? "1" : "0")
                }
              />
            </div>
            <div className="space-y-2">
              <Label>目标文件大小 (KB)</Label>
              <Input
                type="number"
                min={100}
                max={5120}
                value={cv(settings, "compress_target_size", "500")}
                onChange={(e) => set("compress_target_size", e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>
                  最低画质：{cv(settings, "compress_min_quality", "60")}
                </Label>
                <Slider
                  value={[
                    Number(cv(settings, "compress_min_quality", "60")),
                  ]}
                  onValueChange={([v]) =>
                    set("compress_min_quality", String(v))
                  }
                  min={40}
                  max={80}
                  step={1}
                />
              </div>
              <div className="space-y-2">
                <Label>
                  最高画质：{cv(settings, "compress_max_quality", "95")}
                </Label>
                <Slider
                  value={[
                    Number(cv(settings, "compress_max_quality", "95")),
                  ]}
                  onValueChange={([v]) =>
                    set("compress_max_quality", String(v))
                  }
                  min={80}
                  max={100}
                  step={1}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ===== 7. 导出设置 ===== */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Settings2 className="w-5 h-5" />
              导出设置
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>默认导出目录</Label>
              <Input
                placeholder="选择导出目录路径"
                value={cv(settings, "export_default_dir", "")}
                onChange={(e) => set("export_default_dir", e.target.value)}
              />
            </div>
            <div className="flex items-center justify-between">
              <Label>任务完成声音提醒</Label>
              <Switch
                checked={cv(settings, "notification_sound", "1") === "1"}
                onCheckedChange={(v) =>
                  set("notification_sound", v ? "1" : "0")
                }
              />
            </div>
            <div className="flex items-center justify-between">
              <Label>浏览器通知</Label>
              <Switch
                checked={cv(settings, "notification_browser", "1") === "1"}
                onCheckedChange={(v) =>
                  set("notification_browser", v ? "1" : "0")
                }
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
