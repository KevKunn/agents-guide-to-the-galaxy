// Call site in Program.CreateHostBuilder of the Blazor.Server host; UseSecretFiles must be the last configuration call.
using {{APP_PROJECT}}.Hosting;

    public static IHostBuilder CreateHostBuilder(string[] args) {
        var hostBuilder = Host.CreateDefaultBuilder(args)
            .ConfigureLogging(logging => logging.ClearProviders())
            .ConfigureWebHostDefaults(webBuilder => {
                webBuilder.UseStartup<Startup>();
            });
        // ... logging / telemetry registration of the app (in the worked example: UseSigNoz, UseSerilog) ...
        hostBuilder.UseSecretFiles(SecretFiles.DefaultDirectory);
        return hostBuilder;
    }

// If the app has a separate fatal-start logger with its own ConfigurationBuilder, add
// .AddSecretFiles(SecretFiles.DefaultDirectory) as its last source too, so a Slack webhook
// that only exists as a secret also reports a failed start.
