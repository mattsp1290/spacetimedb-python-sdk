// Direct test of Python codegen functionality
use spacetimedb_codegen::{generate, Python};
use spacetimedb_schema::def::{ModuleDef, TableDef, TypeDef, ReducerDef};
use spacetimedb_schema::identifier::Identifier;
use spacetimedb_lib::sats::{AlgebraicType, ProductType, ProductTypeElement};
use spacetimedb_schema::schema::TableSchema;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create a simple test module definition
    let mut module = ModuleDef::new();
    
    // Add a simple table type (User table from the quickstart example)
    let user_type = AlgebraicType::Product(ProductType::new([
        ProductTypeElement::new_named(AlgebraicType::U64, "identity"),
        ProductTypeElement::new_named(
            AlgebraicType::option(AlgebraicType::String), 
            "name"
        ),
        ProductTypeElement::new_named(AlgebraicType::Bool, "online"),
    ]));
    
    let user_type_ref = module.add_type(user_type);
    
    // Add table definition
    let user_table = TableDef {
        name: Identifier::new("User")?,
        product_type_ref: user_type_ref,
        primary_key: Some(vec![0]), // identity field
        indexes: vec![],
        constraints: vec![],
        table_type: spacetimedb_schema::def::TableType::User,
        table_access: spacetimedb_schema::def::TableAccess::Public,
    };
    
    module.add_table(user_table);
    
    // Generate Python code
    let python_lang = Python;
    let generated_files = generate(&module, &python_lang);
    
    println!("Generated {} Python files:", generated_files.len());
    for (filename, content) in generated_files {
        println!("\n=== {} ===", filename);
        println!("{}", content);
        println!("=== End {} ===\n", filename);
    }
    
    Ok(())
}
