import aiosqlite
import asyncio

DATABASE_PATH = "soccer_cards.db"

async def clear_all_tables():
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Get the list of all tables
            async with db.execute("SELECT name FROM sqlite_master WHERE type='table';") as cursor:
                tables = await cursor.fetchall()
                
            for table in tables:
                table_name = table[0]
                # Delete all rows from each table
                await db.execute(f"DELETE FROM {table_name}")
            
            # Commit the changes
            await db.commit()
            
            print("All tables have been cleared.")
    
    except Exception as e:
        print(f"An error occurred: {e}")

  # Replace with the actual card ID you want to delete

asyncio.run(clear_all_tables())
# To execute the function
import asyncio
