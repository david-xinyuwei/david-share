using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Azure.AI.AgentServer.Core;
using Azure.AI.AgentServer.Responses;
using Azure.AI.AgentServer.Responses.Models;

var builder = AgentHost.CreateBuilder(args);
builder.AddResponses<LraEvidenceHandler>(
    options => options.ResilientBackground = true);
builder.Build().Run();

public sealed class LraEvidenceHandler : ResponseHandler
{
    private const int InjectedExitCode = 86;

    private static readonly string[] Checkpoints =
    [
        "accept",
        "validate_input",
        "fingerprint_payload",
        "plan_work",
        "allocate_steps",
        "prepare_context",
        "execute_part_1",
        "execute_part_2",
        "execute_part_3",
        "aggregate_results",
        "verify_order",
        "verify_uniqueness",
        "verify_payload",
        "build_summary",
        "record_metrics",
        "finalize_output",
        "validate_terminal",
        "complete",
    ];

    private static readonly string ProcessInstanceId =
        $"{Environment.MachineName}-{Environment.ProcessId}-{Guid.NewGuid():N}";

    public override async IAsyncEnumerable<ResponseStreamEvent> CreateAsync(
        CreateResponse request,
        ResponseContext context,
        [EnumeratorCancellation] CancellationToken cancellationToken)
    {
        string rawInput = await context.GetInputTextAsync(
            cancellationToken: cancellationToken);
        WorkSpec spec = JsonSerializer.Deserialize<WorkSpec>(rawInput)
            ?? throw new InvalidOperationException("Input must contain a work specification.");
        bool faultEnabled = string.Equals(
            Environment.GetEnvironmentVariable("LRA_ENABLE_FAULT_INJECTION"),
            "true",
            StringComparison.OrdinalIgnoreCase);

        if (spec.CrashAfterStage is not null && !faultEnabled)
        {
            var failed = new ResponseEventStream(context, request);
            yield return failed.EmitCreated();
            yield return failed.EmitFailed(
                "crash_after_stage requires LRA_ENABLE_FAULT_INJECTION=true");
            yield break;
        }

        var stream = context.IsRecovery && context.PersistedResponse is not null
            ? new ResponseEventStream(context, context.PersistedResponse)
            : new ResponseEventStream(context, request);
        int start = context.IsRecovery
            ? context.PersistedResponse?.Output.Count ?? 0
            : 0;

        Log(
            "LRA_ENTRY",
            context,
            spec.WorkId,
            $"mode={(context.IsRecovery ? "recovered" : "fresh")} start={start}");
        yield return stream.EmitCreated();
        yield return stream.EmitInProgress();

        for (int index = start; index < Checkpoints.Length; index++)
        {
            await Task.Delay(spec.StageDelayMs, cancellationToken);
            string checkpoint = Checkpoints[index];
            string resultHash = Sha256(
                $"{spec.Payload}\n{index}\n{checkpoint}");
            var record = new
            {
                schema_version = 2,
                kind = "lra_stage",
                work_id = spec.WorkId,
                payload_sha256 = Sha256(spec.Payload),
                stage_index = index,
                stage_name = checkpoint,
                stage_count = Checkpoints.Length,
                stage_result_sha256 = resultHash,
                entry_mode = context.IsRecovery ? "recovered" : "fresh",
                process_instance_id = ProcessInstanceId,
            };
            foreach (ResponseStreamEvent responseEvent in stream.OutputItemMessage(
                JsonSerializer.Serialize(record)))
            {
                yield return responseEvent;
            }
            yield return stream.Checkpoint();
            Log("LRA_STAGE_COMMITTED", context, spec.WorkId, $"stage={index}");

            if (
                faultEnabled
                && !context.IsRecovery
                && spec.CrashAfterStage == index)
            {
                Log(
                    "LRA_INJECTED_PROCESS_LOSS",
                    context,
                    spec.WorkId,
                    $"after_stage={index} exit_code={InjectedExitCode}");
                await Task.Delay(500, CancellationToken.None);
                Environment.Exit(InjectedExitCode);
            }
        }

        Log("LRA_COMPLETED", context, spec.WorkId);
        yield return stream.EmitCompleted();
    }

    private static void Log(
        string eventName,
        ResponseContext context,
        string workId,
        string details = "")
    {
        Console.WriteLine(
            $"{eventName} at_utc={DateTimeOffset.UtcNow:O} "
            + $"response_id={context.ResponseId} work_id={workId} "
            + $"instance={ProcessInstanceId} {details}".TrimEnd());
    }

    private static string Sha256(string value) =>
        Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value)))
            .ToLowerInvariant();

    private sealed record WorkSpec(
        [property: JsonPropertyName("work_id")] string WorkId,
        [property: JsonPropertyName("payload")] string Payload,
        [property: JsonPropertyName("crash_after_stage")] int? CrashAfterStage,
        [property: JsonPropertyName("stage_delay_ms")] int StageDelayMs);
}
