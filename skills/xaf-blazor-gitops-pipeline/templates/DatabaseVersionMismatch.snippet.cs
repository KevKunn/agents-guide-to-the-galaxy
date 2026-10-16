using DevExpress.ExpressApp;
using DevExpress.ExpressApp.Blazor;

namespace {{APP_PROJECT}};

public class {{APPLICATION_CLASS}} : BlazorApplication {
    public {{APPLICATION_CLASS}}() {
        ApplicationName = "{{APPLICATION_NAME}}";
        CheckCompatibilityType = DevExpress.ExpressApp.CheckCompatibilityType.DatabaseSchema;
        DatabaseVersionMismatch += {{APPLICATION_CLASS}}_DatabaseVersionMismatch;
    }
    internal void {{APPLICATION_CLASS}}_DatabaseVersionMismatch(object sender, DatabaseVersionMismatchEventArgs e) {
        e.Updater.Update();
        e.Handled = true;
    }
}
